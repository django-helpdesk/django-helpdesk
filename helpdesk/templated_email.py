import os
import logging
from smtplib import SMTPException

from django.conf import settings
from django.utils.safestring import mark_safe
from seed.lib.superperms.orgs.models import Organization
from seed.models.email_settings import ImporterSenderMapping
from seed.utils.seed_send_email import get_email_backend

logger = logging.getLogger(__name__)

DEBUGGING = False


def add_custom_header(recipients):
    """
    :return recipients: list of strings
    :return header: a comma-separated string
    """
    address_list = []
    header = ''

    if isinstance(recipients, str):
        if ',' in recipients:
            # Lower string, split into list, strip individual strings, and then assign
            address_list = recipients.lower().split(',')
            address_list = list(map(str.strip, address_list))
            header = ','.join(address_list)
        else:
            # Lower string, strip, assign to header, make a list again
            recipients = recipients.lower().strip()
            header = recipients
            address_list = [recipients]
    elif isinstance(recipients, list):
        # Map strip to list, map lower to list, turn into a list again, assign
        address_list = list(map(str.lower, map(str.strip, recipients)))
        header = ','.join(address_list)

    return address_list, header


def send_templated_mail(template_name,
                        context,
                        recipients,
                        sender=None,
                        bcc=None,
                        fail_silently=False,
                        files=None,
                        organization=None,
                        extra_headers=None):
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
    from django.core.mail import EmailMultiAlternatives, BadHeaderError
    from django.template import engines
    from_string = engines['django'].from_string

    from helpdesk.models import EmailTemplate
    from helpdesk.settings import HELPDESK_EMAIL_SUBJECT_TEMPLATE, \
        HELPDESK_EMAIL_FALLBACK_LOCALE

    headers = extra_headers or {}
    for key, value in headers.items():
        headers[key] = value.strip()

    locale = context['queue'].get('locale') or HELPDESK_EMAIL_FALLBACK_LOCALE

    org_id = context['queue'].get('organization_id', None)
    org = Organization.objects.get(id=org_id)

    importer_sender_id = context['queue'].get('importer_sender_id', None)
    backend = None
    if importer_sender_id:
        importer_sender_settings = ImporterSenderMapping.objects.get(id=importer_sender_id)
        sender_address = importer_sender_settings.sender.from_address
        backend = get_email_backend(None, importer_sender_settings.sender)
    elif org:
        sender_address = org.sender.from_address
        backend = get_email_backend(org, None)
    else:
        sender_address = sender

    try:
        t = EmailTemplate.objects.get(template_name__iexact=template_name, locale=locale, organization=organization)
    except EmailTemplate.DoesNotExist:
        try:
            t = EmailTemplate.objects.get(template_name__iexact=template_name, locale__isnull=True, organization=organization)
        except EmailTemplate.DoesNotExist:
            logger.warning('template "%s" does not exist, no mail sent', template_name)
            return  # just ignore if template doesn't exist

    subject_part = from_string(
        HELPDESK_EMAIL_SUBJECT_TEMPLATE % {
            "subject": t.subject
        }).render(context).replace('\n', '').replace('\r', '')

    footer_file = os.path.join('helpdesk', locale, 'email_text_footer.txt')

    text_part = from_string(
        "%s\n\n{%% include '%s' %%}" % (t.plain_text, footer_file)
    ).render(context)

    # file found in helpdesk/templates/helpdesk/[locale]/
    email_html_base_file = os.path.join('helpdesk', locale, 'email_html_base.html')
    # keep new lines in html emails
    if 'comment' in context:
        context['comment'] = mark_safe(context['comment'].replace('\r\n', '<br>'))

    html_part = from_string(
        "{%% extends '%s' %%}"
        "{%% block title %%}%s{%% endblock %%}"
        "{%% block content %%}%s{%% endblock %%}" %
        (email_html_base_file, t.heading, t.html)
    ).render(context)

    recipients, headers['X-BEAMHelpdesk-Delivered'] = add_custom_header(recipients)

    msg = EmailMultiAlternatives(subject_part, text_part,
                                 sender_address or settings.DEFAULT_FROM_EMAIL,
                                 recipients, bcc=bcc,
                                 headers=headers)
    msg.attach_alternative(html_part, "text/html")
    if backend:
        msg.connection = backend

    if files:
        for filename, filefield in files:
            filefield.open('rb')
            content = filefield.read()
            msg.attach(filename, content)
            filefield.close()

    logger.debug('Sending emails.')
    try:
        if DEBUGGING:
            return 0
        else:
            msg.send()
    except SMTPException as e:
        logger.exception('SMTPException raised while sending email from {} to {}'.format(sender, recipients))
        if not fail_silently:
            raise e
        return 0
    except BadHeaderError as e1:
        logger.exception('BadHeaderError raised while sending email from {} to {}.'.format(sender, recipients))
        if not fail_silently:
            raise e1
        return 0
    except Exception as e2:
        logger.exception('Raised failure while sending email from {} to {}'.format(sender, recipients))
        if not fail_silently:
            raise e2
        return 0
