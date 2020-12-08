"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

lib.py - Common functions (eg multipart e-mail)
"""

import logging
import mimetypes
import os
from datetime import date, timedelta
from smtplib import SMTPException
from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.core.mail import mail_admins
from django.urls import reverse, set_script_prefix, clear_script_prefix
from helpdesk import settings as helpdesk_settings

from base.models import get_technical_service

try:
    # Python 2 support
    from base64 import urlsafe_b64encode as b64encode
except ImportError:
    # Python 3 support
    from base64 import encodebytes as b64encode
try:
    # Python 2 support
    from base64 import urlsafe_b64decode as b64decode
except ImportError:
    # Python 3 support
    from base64 import decodebytes as b64decode

from django.conf import settings
from django.db.models import Q
from django.utils import six
from django.utils.encoding import smart_text
from django.utils.safestring import mark_safe

from helpdesk.models import Attachment, EmailTemplate

User = get_user_model()


def send_templated_mail(template_name,
                        context,
                        recipients,
                        sender=None,
                        bcc=None,
                        fail_silently=False,
                        files=None):
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
            mail_admins(
                'Template de mail introuvable',
                "Le template de mail \"%s\" n'existe pas, le mail n'a pas pu être envoyé" % template_name
            )
            return  # just ignore if template doesn't exist

    subject_part = from_string(
        HELPDESK_EMAIL_SUBJECT_TEMPLATE % {
            "subject": t.subject
        }).render(context).replace('\n', '').replace('\r', '')

    footer_file = os.path.join('helpdesk', locale, 'email_text_footer.txt')

    # Do HTML part first in order to mark safe the HTML
    email_html_base_file = os.path.join('helpdesk', locale, 'email_html_base.html')
    for field in ('comment', 'description', 'resolution'):
        if field in context['ticket']:
            context['ticket'][field] = mark_safe(context['ticket'][field])

    # Set script url to the site URL in order to have absolute url in the mail
    set_script_prefix(settings.SITE_URL)

    # Add feedback_survey_url  to context if it is a closed ticket
    if template_name == 'closed_submitter':
        context['feedback_survey_url'] = reverse(
            'helpdesk:feedback_survey',
            kwargs={'ticket_id': context['ticket']['id']}
        )

    html_part = from_string(
        "{%% extends '%s' %%}"
        "{%% block title %%}%s{%% endblock %%}"
        "{%% block content %%}%s{%% endblock %%}" %
        (email_html_base_file, t.heading, t.html)
    ).render(context)

    # Then use BeautifulSoup to extract text from HTML fields
    for field in ('comment', 'description', 'resolution'):
        if field in context['ticket']:
            context['ticket'][field] = BeautifulSoup(context['ticket'][field], 'html.parser').get_text()

    text_part = from_string(
        "%s\n\n{%% include '%s' %%}" % (t.plain_text, footer_file)
    ).render(context)

    clear_script_prefix()

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
                if six.PY3:
                    msg.attach_file(filefield.path)
                else:
                    with open(filefield.path, 'rb') as attachedfile:
                        content = attachedfile.read()
                        msg.attach(filename, content)

    print('Sending email to: %s' % ', '.join(recipients))

    try:
        return msg.send()
    except SMTPException as e:
        mail_admins(
            'Erreur envoi de mail Helpdesk',
            "Une excpetion SMTP a eu lieu lors de l'envoi d'un mail à : %s.\n\n%s" % (', '.join(recipients), e)
        )
        if not fail_silently:
            raise e
        return 0


def query_to_dict(results, descriptions):
    """
    Replacement method for cursor.dictfetchall() as that method no longer
    exists in psycopg2, and I'm guessing in other backends too.

    Converts the results of a raw SQL query into a list of dictionaries, suitable
    for use in templates etc.
    """

    output = []
    for data in results:
        row = {}
        i = 0
        for column in descriptions:
            row[column[0]] = data[i]
            i += 1

        output.append(row)
    return output


def apply_query(queryset, params):
    """
    Apply a dict-based set of filters & parameters to a queryset.

    queryset is a Django queryset, eg MyModel.objects.all() or
             MyModel.objects.filter(user=request.user)

    params is a dictionary that contains the following:
        filtering: A dict of Django ORM filters (-1 will add the isnull lookup), eg:
            {'user__id__in': [1, 3, 103], 'title__contains': 'foo', 'customer__id__in': [-1]}

        created_relative: A dict with the number of days from which to filter the created date, and the direction, eg:
            {'days': 30, 'direction': 'before'}

        search_string: A freetext search string

        sorting: The name of the column to sort by
        sortreverse: The direction of the ordering
    """
    for key in params['filtering'].keys():
        object_ids = params['filtering'][key]
        # Check if unnassigned has been selected in order to add the isnull lookup and perform a OR
        if -1 in object_ids:
            null_key = key.replace('__in', '__isnull')
            queryset = queryset.filter(Q(**{key: object_ids}) | Q(**{null_key: True}))
        else:
            queryset = queryset.filter(**{key: object_ids})

    if params['created_relative'].get('days') and params['created_relative'].get('direction'):
        relative_date = date.today() - timedelta(params['created_relative']['days'])
        operation = 'created__lt'  # It is before by default
        if params['created_relative']['direction'] == 'after':
            operation = 'created__gt'
        queryset = queryset.filter(**{operation: relative_date.strftime('%Y-%m-%d')})

    search = params.get('search_string')
    if search:
        qset = (
            Q(id__iexact=search) |
            Q(title__icontains=search) |
            Q(customer__group__name__icontains=search) |
            Q(site__name__icontains=search) |
            Q(customer_product__product__name__icontains=search) |
            Q(customer_product__comment__icontains=search) |
            Q(description__icontains=search) |
            Q(resolution__icontains=search) |
            Q(submitter_email__icontains=search) |
            Q(ticketcustomfieldvalue__value__icontains=search)
        )

        # Distinct works, when there are multiple custom fields
        queryset = queryset.filter(qset).distinct()

    sorting = params.get('sorting')
    if sorting:
        sortreverse = params.get('sortreverse')
        if sortreverse and sorting[0] != '-':
            sorting = "-%s" % sorting
        queryset = queryset.order_by(sorting)

    return queryset


def ticket_template_context(ticket):
    context = {}

    for field in ('id', 'title', 'created', 'modified', 'submitter_email',
                  'status', 'get_status_display', 'on_hold', 'description',
                  'resolution', 'priority', 'get_priority_display',
                  'last_escalation', 'ticket', 'ticket_for_url',
                  'get_status', 'ticket_url', 'staff_url', '_get_assigned_to',
                  'merged_to'
                  ):
        attr = getattr(ticket, field, None)
        if callable(attr):
            context[field] = '%s' % attr()
        else:
            context[field] = attr
    context['assigned_to'] = context['_get_assigned_to']

    return context


def queue_template_context(queue):
    context = {}

    for field in ('title', 'slug', 'email_address', 'phone_number', 'from_address', 'locale'):
        attr = getattr(queue, field, None)
        if callable(attr):
            context[field] = attr()
        else:
            context[field] = attr

    return context


def safe_template_context(ticket):
    """
    Return a dictionary that can be used as a template context to render
    comments and other details with ticket or queue parameters. Note that
    we don't just provide the Ticket & Queue objects to the template as
    they could reveal confidential information. Just imagine these two options:
        * {{ ticket.queue.email_box_password }}
        * {{ ticket.assigned_to.password }}

    Ouch!

    The downside to this is that if we make changes to the model, we will also
    have to update this code. Perhaps we can find a better way in the future.
    """

    context = {
        'queue': queue_template_context(ticket.queue),
        'ticket': ticket_template_context(ticket),
    }
    context['ticket']['queue'] = context['queue']

    return context


def text_is_spam(text, request):
    # Based on a blog post by 'sciyoshi':
    # http://sciyoshi.com/blog/2008/aug/27/using-akismet-djangos-new-comments-framework/
    # This will return 'True' is the given text is deemed to be spam, or
    # False if it is not spam. If it cannot be checked for some reason, we
    # assume it isn't spam.
    from django.contrib.sites.models import Site
    from django.core.exceptions import ImproperlyConfigured
    try:
        from helpdesk.akismet import Akismet
    except ImportError:
        return False
    try:
        site = Site.objects.get_current()
    except ImproperlyConfigured:
        site = Site(domain='configure-django-sites.com')

    ak = Akismet(
        blog_url='http://%s/' % site.domain,
        agent='django-helpdesk',
    )

    if hasattr(settings, 'TYPEPAD_ANTISPAM_API_KEY'):
        ak.setAPIKey(key=settings.TYPEPAD_ANTISPAM_API_KEY)
        ak.baseurl = 'api.antispam.typepad.com/1.1/'
    elif hasattr(settings, 'AKISMET_API_KEY'):
        ak.setAPIKey(key=settings.AKISMET_API_KEY)
    else:
        return False

    if ak.verify_key():
        ak_data = {
            'user_ip': request.META.get('REMOTE_ADDR', '127.0.0.1'),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'referrer': request.META.get('HTTP_REFERER', ''),
            'comment_type': 'comment',
            'comment_author': '',
        }

        return ak.comment_check(smart_text(text), data=ak_data)

    return False


def process_attachments(followup, attached_files):
    max_email_attachment_size = getattr(settings, 'HELPDESK_MAX_EMAIL_ATTACHMENT_SIZE', 512000)
    attachments = []

    for attached in attached_files:
        filename = smart_text(attached.name)
        if attached.size:
            att = Attachment.objects.create(
                followup=followup,
                file=attached,
                filename=filename,
                mime_type=attached.content_type or
                mimetypes.guess_type(filename, strict=False)[0] or
                'application/octet-stream',
                size=attached.size,
            )

            if attached.size < max_email_attachment_size:
                # Only files smaller than 512kb (or as defined in
                # settings.HELPDESK_MAX_EMAIL_ATTACHMENT_SIZE) are sent via email.
                attachments.append([filename, att.file])
            else:
                print('%s est trop lourd pour être envoyé par mail : %skb' % (filename, attached.size / 1000))
        else:
            print('%s has no size' % filename)

    return attachments


def get_assignable_users():
    if helpdesk_settings.HELPDESK_STAFF_ONLY_TICKET_OWNERS:
        # Try to show only members of the technical service
        technical_service = get_technical_service()
        if technical_service:
            assignable_users = User.objects.filter(is_active=True, groups=technical_service)
        else:
            # Or if it doesn't exist, only staff users
            assignable_users = User.objects.filter(is_active=True, is_staff=True)
    else:
        assignable_users = User.objects.filter(is_active=True)
    return assignable_users.order_by(User.USERNAME_FIELD)


def calc_tickets_first_answer_statistics(tickets):
    """ Calculation of the tickets first answer time average and the percentage of which are under one hour """
    first_answer_time_average = percentage_under_one_hour = None
    total_first_answer_times = timedelta()
    number_under_one_hour = []
    for ticket in tickets:
        first_answer_time = ticket.get_time_first_answer()
        if first_answer_time:
            total_first_answer_times += first_answer_time
            number_under_one_hour.append(first_answer_time < timedelta(hours=1))
    count = len(number_under_one_hour)
    if count > 0:
        first_answer_time_average = total_first_answer_times / count
        percentage_under_one_hour = round(number_under_one_hour.count(True) / count * 100)
    return first_answer_time_average, percentage_under_one_hour
