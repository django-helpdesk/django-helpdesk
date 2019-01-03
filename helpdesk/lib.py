"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

lib.py - Common functions (eg multipart e-mail)
"""

import logging
import mimetypes
import os

from django.conf import settings
from django.db.models import Q
from django.utils.encoding import smart_text, smart_str
from django.utils.safestring import mark_safe

from helpdesk.models import Attachment, EmailTemplate

from model_utils import Choices

from base64 import b64encode
from base64 import b64decode

import json

logger = logging.getLogger('helpdesk')


def query_to_base64(query):
    """
    Converts a query dict object to a base64-encoded bytes object.
    """
    return b64encode(json.dumps(query).encode('UTF-8'))


def query_from_base64(b64data):
    """
    Converts base64-encoded bytes object back to a query dict object.
    """
    return json.loads(b64decode(b64data).decode('utf-8'))


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
        filtering: A dict of Django ORM filters, eg:
            {'user__id__in': [1, 3, 103], 'title__contains': 'foo'}

        search_string: A freetext search string

        sorting: The name of the column to sort by
    """
    for key in params['filtering'].keys():
        filter = {key: params['filtering'][key]}
        queryset = queryset.filter(**filter)

    search = params.get('search_string', None)
    if search:
        qset = (
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(resolution__icontains=search) |
            Q(submitter_email__icontains=search)
        )

        queryset = queryset.filter(qset)

    sorting = params.get('sorting', None)
    if sorting:
        sortreverse = params.get('sortreverse', None)
        if sortreverse:
            sorting = "-%s" % sorting
        queryset = queryset.order_by(sorting)

    return queryset


def ticket_template_context(ticket):
    context = {}

    for field in ('title', 'created', 'modified', 'submitter_email',
                  'status', 'get_status_display', 'on_hold', 'description',
                  'resolution', 'priority', 'get_priority_display',
                  'last_escalation', 'ticket', 'ticket_for_url',
                  'get_status', 'ticket_url', 'staff_url', '_get_assigned_to'
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

    for field in ('title', 'slug', 'email_address', 'from_address', 'locale'):
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
        ak.baseurl = 'api.antispam.typepad.com/1.1/'
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
    max_email_attachment_size = getattr(settings, 'MAX_EMAIL_ATTACHMENT_SIZE', 512000)
    attachments = []

    for attached in attached_files:

        if attached.size:
            filename = smart_text(attached.name)
            att = Attachment(
                followup=followup,
                file=attached,
                filename=filename,
                mime_type=attached.content_type or
                mimetypes.guess_type(filename, strict=False)[0] or
                'application/octet-stream',
                size=attached.size,
            )
            att.save()

            if attached.size < max_email_attachment_size:
                # Only files smaller than 512kb (or as defined in
                # settings.MAX_EMAIL_ATTACHMENT_SIZE) are sent via email.
                attachments.append([filename, att.file])

    return attachments


ORDER_COLUMN_CHOICES = Choices(
    ('0', 'id'),
    ('2', 'priority'),
    ('3', 'title'),
    ('4', 'queue'),
    ('5', 'status'),
    ('6', 'created'),
    ('7', 'due_date'),
    ('8', 'assigned_to')
)


def query_tickets_by_args(objects, order_by, **kwargs):
    """
    This function takes in a list of ticket objects from the views and throws it
    to the datatables on ticket_list.html. If a search string was entered, this
    function filters existing dataset on search string and returns a filtered
    filtered list. The `draw`, `length` etc parameters are for datatables to
    display meta data on the table contents. The returning queryset is passed
    to a Serializer called TicketSerializer in serializers.py.
    """
    draw = int(kwargs.get('draw', None)[0])
    length = int(kwargs.get('length', None)[0])
    start = int(kwargs.get('start', None)[0])
    search_value = kwargs.get('search[value]', None)[0]
    order_column = kwargs.get('order[0][column]', None)[0]
    order = kwargs.get('order[0][dir]', None)[0]

    order_column = ORDER_COLUMN_CHOICES[order_column]
    # django orm '-' -> desc
    if order == 'desc':
        order_column = '-' + order_column

    queryset = objects.all().order_by(order_by)
    total = queryset.count()

    if search_value:
        queryset = queryset.filter(Q(id__icontains=search_value) |
                                   Q(priority__icontains=search_value) |
                                   Q(title__icontains=search_value) |
                                   Q(queue__title__icontains=search_value) |
                                   Q(status__icontains=search_value) |
                                   Q(created__icontains=search_value) |
                                   Q(due_date__icontains=search_value) |
                                   Q(assigned_to__email__icontains=search_value))

    count = queryset.count()
    queryset = queryset.order_by(order_column)[start:start + length]
    return {
        'items': queryset,
        'count': count,
        'total': total,
        'draw': draw
    }
