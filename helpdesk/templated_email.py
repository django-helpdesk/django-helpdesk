import os
import mimetypes
import logging
from smtplib import SMTPException

from django.utils.safestring import mark_safe

logger = logging.getLogger('helpdesk')


def send_templated_mail(template_name,
                        context,
                        recipients,
                        sender=None,
                        bcc=None,
                        fail_silently=False,
                        files=None,
                        extra_headers={}):
    """
    send_templated_mail() is a wrapper around Django's e-mail routines that
    allows us to easily send multipart (text/plain & text/html) e-mails using
    templates that are stored in the database. This lets the admin provide
    both a text and a HTML template for each message.

    template_name is the slug of the template to use for this message (see
        models.EmailTemplate)

    context is a dictionary to be used when rendering the template

    recipients can be either a string, eg 'a@b.com', or a list of strings.

    sender should contain a string, eg 'My Site <me@z.com>'. If you leave it
        blank, it'll use settings.DEFAULT_FROM_EMAIL as a fallback.

    bcc is an optional list of addresses that will receive this message as a
        blind carbon copy.

    fail_silently is passed to Django's mail routine. Set to 'True' to ignore
        any errors at send time.

    files can be a list of tuples. Each tuple should be a filename to attach,
        along with the File objects to be read. files can be blank.

    extra_headers is a dictionary of extra email headers, needed to process
        email replies and keep proper threading.

    """
    from django.core.mail import EmailMultiAlternatives
    from django.template import engines
    from_string = engines['django'].from_string

    from helpdesk.models import EmailTemplate
    from helpdesk.settings import HELPDESK_EMAIL_SUBJECT_TEMPLATE, \
        HELPDESK_EMAIL_FALLBACK_LOCALE

    locale = context['queue'].get('locale') or HELPDESK_EMAIL_FALLBACK_LOCALE

    try:
        t = EmailTemplate.objects.get(template_name__iexact=template_name, locale=locale)
    except EmailTemplate.DoesNotExist:
        try:
            t = EmailTemplate.objects.get(template_name__iexact=template_name, locale__isnull=True)
        except EmailTemplate.DoesNotExist:
            logger.warning('template "%s" does not exist, no mail sent', template_name)
            return  # just ignore if template doesn't exist

    subject_part = from_string(
        HELPDESK_EMAIL_SUBJECT_TEMPLATE % {
            "subject": t.subject
        }).render(context).replace('\n', '').replace('\r', '')

    footer_file = os.path.join('helpdesk', locale, 'email_text_footer.txt')

    text_part = from_string(
        "%s{%% include '%s' %%}" % (t.plain_text, footer_file)
    ).render(context)

    email_html_base_file = os.path.join('helpdesk', locale, 'email_html_base.html')
    # keep new lines in html emails
    if 'comment' in context:
        context['comment'] = mark_safe(context['comment'].replace('\r\n', '<br>'))

    html_part = from_string(
        "{%% extends '%s' %%}{%% block title %%}"
        "%s"
        "{%% endblock %%}{%% block content %%}%s{%% endblock %%}" %
        (email_html_base_file, t.heading, t.html)
    ).render(context)

    if isinstance(recipients, str):
        if recipients.find(','):
            recipients = recipients.split(',')
    elif type(recipients) != list:
        recipients = [recipients]

    msg = EmailMultiAlternatives(subject_part, text_part,
                                 sender or settings.DEFAULT_FROM_EMAIL,
                                 recipients, bcc=bcc)
    msg.attach_alternative(html_part, "text/html")

    if files:
        for filename, filefield in files:
            mime = mimetypes.guess_type(filename)
            if mime[0] is not None and mime[0] == "text/plain":
                with open(filefield.path, 'r') as attachedfile:
                    content = attachedfile.read()
                    msg.attach(filename, content)
            else:
                msg.attach_file(filefield.path)
    logger.debug('Sending email to: {!r}'.format(recipients))

    try:
        return msg.send()
    except SMTPException as e:
        logger.exception('SMTPException raised while sending email to {}'.format(recipients))
        if not fail_silently:
            raise e
        return 0
