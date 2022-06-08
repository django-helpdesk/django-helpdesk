"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

lib.py - Common functions (eg multipart e-mail)
"""

import logging
from mimetypes import guess_type

from django.conf import settings
from django.utils.encoding import smart_text

from helpdesk.models import FollowUpAttachment


logger = logging.getLogger(__name__)


def ticket_template_context(ticket):
    context = {}
    empty_text = ''

    for field in ('title', 'created', 'modified', 'submitter_email',
                  'status', 'get_status_display', 'on_hold', 'description',
                  'resolution', 'priority', 'get_priority_display',
                  'last_escalation', 'ticket', 'ticket_for_url', 'merged_to',
                  'get_status', 'ticket_url', 'staff_url', '_get_assigned_to',
                  'contact_name', 'contact_email', 'building_name', 'building_address', 'pm_id', 'building_id'
                  ):
        attr = getattr(ticket, field, None)
        if callable(attr):
            context[field] = '%s' % attr()
        elif attr is None or attr == '':
            context[field] = empty_text
        else:
            context[field] = attr
    context['assigned_to'] = context['_get_assigned_to']

    extra_data = getattr(ticket, 'extra_data', {})
    for field, value in extra_data.items():
        if value is None or value == '':
            context[field] = empty_text
        else:
            context[field] = '%s' % value

    return context


def queue_template_context(queue):
    context = {}

    for field in ('title', 'slug', 'email_address', 'from_address', 'locale', 'organization_id', 'importer_sender_id'):
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
        * {{ ticket.queue.password }}
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
        from akismet import Akismet
    except ImportError:
        return False
    try:
        site = Site.objects.get_current()
    except ImproperlyConfigured:
        site = Site(domain='configure-django-sites.com')

    # see https://akismet.readthedocs.io/en/latest/overview.html#using-akismet

    apikey = None

    if hasattr(settings, 'TYPEPAD_ANTISPAM_API_KEY'):
        apikey = settings.TYPEPAD_ANTISPAM_API_KEY
    elif hasattr(settings, 'PYTHON_AKISMET_API_KEY'):
        # new env var expected by python-akismet package
        apikey = settings.PYTHON_AKISMET_API_KEY
    elif hasattr(settings, 'AKISMET_API_KEY'):
        # deprecated, but kept for backward compatibility
        apikey = settings.AKISMET_API_KEY
    else:
        return False

    ak = Akismet(
        blog_url='http://%s/' % site.domain,
        key=apikey,
    )

    if hasattr(settings, 'TYPEPAD_ANTISPAM_API_KEY'):
        ak.baseurl = 'api.antispam.typepad.com/1.1/'

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
        try:
            if attached.size:
                filename = smart_text(attached.name)
                att = FollowUpAttachment(
                    followup=followup,
                    file=attached,
                    filename=filename,
                    mime_type=attached.content_type or
                    guess_type(filename, strict=False)[0] or
                    'application/octet-stream',
                    size=attached.size,
                )
                att.save()

                if attached.size < max_email_attachment_size:
                    # Only files smaller than 512kb (or as defined in
                    # settings.HELPDESK_MAX_EMAIL_ATTACHMENT_SIZE) are sent via email.
                    attachments.append([filename, att.file])
        except Exception as e:
            logger.exception('Exception occurred while processing an attachment.')

    return attachments


def format_time_spent(time_spent):
    """Format time_spent attribute to "[H]HHh:MMm" text string to be allign in
    all graphical outputs
    """

    if time_spent:
        time_spent = "{0:02d}h:{1:02d}m".format(
            time_spent.seconds // 3600,
            time_spent.seconds // 60 % 60,
        )
    else:
        time_spent = ""
    return time_spent
