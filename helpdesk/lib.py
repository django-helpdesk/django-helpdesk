"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

lib.py - Common functions (eg multipart e-mail)
"""

chart_colours = ('80C65A', '990066', 'FF9900', '3399CC', 'BBCCED', '3399CC', 'FFCC33')

try:
    from base64 import urlsafe_b64encode as b64encode
except ImportError:
    from base64 import encodestring as b64encode
try:
    from base64 import urlsafe_b64decode as b64decode
except ImportError:
    from base64 import decodestring as b64decode

from django.utils.encoding import smart_str

def send_templated_mail(template_name, email_context, recipients, sender=None, bcc=None, fail_silently=False, files=None):
    """
    send_templated_mail() is a warpper around Django's e-mail routines that
    allows us to easily send multipart (text/plain & text/html) e-mails using
    templates that are stored in the database. This lets the admin provide
    both a text and a HTML template for each message.

    template_name is the slug of the template to use for this message (see
        models.EmailTemplate)

    email_context is a dictionary to be used when rendering the template

    recipients can be either a string, eg 'a@b.com', or a list of strings.

    sender should contain a string, eg 'My Site <me@z.com>'. If you leave it
        blank, it'll use settings.DEFAULT_FROM_EMAIL as a fallback.

    bcc is an optional list of addresses that will receive this message as a
        blind carbon copy.

    fail_silently is passed to Django's mail routine. Set to 'True' to ignore
        any errors at send time.

    files can be a list of file paths to be attached, or it can be left blank.
        eg ('/tmp/file1.txt', '/tmp/image.png')

    """
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    from django.template import loader, Context

    from helpdesk.models import EmailTemplate
    import os

    context = Context(email_context)
    locale = context['queue'].get('locale', 'en')

    t = None
    try:
        t = EmailTemplate.objects.get(template_name__iexact=template_name, locale=locale)
    except EmailTemplate.DoesNotExist:
        pass

    if not t:
        try:
            t = EmailTemplate.objects.get(template_name__iexact=template_name, locale__isnull=True)
        except EmailTemplate.DoesNotExist:
            return # just ignore if template doesn't exist

    if not sender:
        sender = settings.DEFAULT_FROM_EMAIL

    footer_file = os.path.join('helpdesk', locale, 'email_text_footer.txt')

    text_part = loader.get_template_from_string(
        "%s{%% include '%s' %%}" % (t.plain_text, footer_file)
        ).render(context)

    email_html_base_file = os.path.join('helpdesk', locale, 'email_html_base.html')


    ''' keep new lines in html emails '''
    from django.utils.safestring import mark_safe

    if context.has_key('comment'):
        html_txt = context['comment']
        html_txt = html_txt.replace('\r\n', '<br>')
        context['comment'] = mark_safe(html_txt)

    html_part = loader.get_template_from_string(
        "{%% extends '%s' %%}{%% block title %%}%s{%% endblock %%}{%% block content %%}%s{%% endblock %%}" % (email_html_base_file, t.heading, t.html)
        ).render(context)

    subject_part = loader.get_template_from_string(
        "{{ ticket.ticket }} {{ ticket.title|safe }} %s" % t.subject
        ).render(context)

    if type(recipients) == str:
        if recipients.find(','):
            recipients = recipients.split(',')
    elif type(recipients) != list:
        recipients = [recipients,]

    msg = EmailMultiAlternatives(   subject_part,
                                    text_part,
                                    sender,
                                    recipients,
                                    bcc=bcc)
    msg.attach_alternative(html_part, "text/html")

    if files:
        if type(files) != list:
            files = [files,]

        for file in files:
            msg.attach_file(file)

    return msg.send(fail_silently)


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
    Apply a dict-based set of filters & paramaters to a queryset.

    queryset is a Django queryset, eg MyModel.objects.all() or
             MyModel.objects.filter(user=request.user)

    params is a dictionary that contains the following:
        filtering: A dict of Django ORM filters, eg:
            {'user__id__in': [1, 3, 103], 'title__contains': 'foo'}
        other_filter: Another filter of some type, most likely a
            set of Q() objects.
        sorting: The name of the column to sort by
    """
    for key in params['filtering'].keys():
        filter = {key: params['filtering'][key]}
        queryset = queryset.filter(**filter)

    if params.get('other_filter', None):
        # eg a Q() set
        queryset = queryset.filter(params['other_filter'])

    if params.get('sorting', None):
        if params.get('sortreverse', None):
            params['sorting'] = "-%s" % params['sorting']
        queryset = queryset.order_by(params['sorting'])

    return queryset


def safe_template_context(ticket):
    """
    Return a dictionary that can be used as a template context to render
    comments and other details with ticket or queue paramaters. Note that
    we don't just provide the Ticket & Queue objects to the template as
    they could reveal confidential information. Just imagine these two options:
        * {{ ticket.queue.email_box_password }}
        * {{ ticket.assigned_to.password }}

    Ouch!

    The downside to this is that if we make changes to the model, we will also
    have to update this code. Perhaps we can find a better way in the future.
    """

    context = {
        'queue': {},
        'ticket': {},
        }
    queue = ticket.queue

    for field in (  'title', 'slug', 'email_address', 'from_address', 'locale'):
        attr = getattr(queue, field, None)
        if callable(attr):
            context['queue'][field] = attr()
        else:
            context['queue'][field] = attr

    for field in (  'title', 'created', 'modified', 'submitter_email',
                    'status', 'get_status_display', 'on_hold', 'description',
                    'resolution', 'priority', 'get_priority_display',
                    'last_escalation', 'ticket', 'ticket_for_url',
                    'get_status', 'ticket_url', 'staff_url', '_get_assigned_to'
                 ):
        attr = getattr(ticket, field, None)
        if callable(attr):
            context['ticket'][field] = '%s' % attr()
        else:
            context['ticket'][field] = attr

    context['ticket']['queue'] = context['queue']
    context['ticket']['assigned_to'] = context['ticket']['_get_assigned_to']

    return context


def text_is_spam(text, request):
    # Based on a blog post by 'sciyoshi':
    # http://sciyoshi.com/blog/2008/aug/27/using-akismet-djangos-new-comments-framework/
    # This will return 'True' is the given text is deemed to be spam, or
    # False if it is not spam. If it cannot be checked for some reason, we
    # assume it isn't spam.
    from django.contrib.sites.models import Site
    from django.conf import settings
    try:
        from helpdesk.akismet import Akismet
    except:
        return False

    ak = Akismet(
        blog_url='http://%s/' % Site.objects.get(pk=settings.SITE_ID).domain,
        agent='django-helpdesk',
    )

    if hasattr(settings, 'TYPEPAD_ANTISPAM_API_KEY'):
        ak.setAPIKey(key = settings.TYPEPAD_ANTISPAM_API_KEY)
        ak.baseurl = 'api.antispam.typepad.com/1.1/'
    elif hasattr(settings, 'AKISMET_API_KEY'):
        ak.setAPIKey(key = settings.AKISMET_API_KEY)
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

        return ak.comment_check(smart_str(text), data=ak_data)

    return False
