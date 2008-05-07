"""                                     .. 
Jutda Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

lib.py - Common functions (eg multipart e-mail)
"""
def send_templated_mail(template_name, email_context, recipients, sender=None, bcc=None, fail_silently=False, files=None):
    from helpdesk.models import EmailTemplate
    from django.core.mail import EmailMultiAlternatives
    from django.template import loader, Context
    from django.conf import settings

    t = EmailTemplate.objects.get(template_name__iexact=template_name)

    if not sender:
        sender = settings.DEFAULT_FROM_EMAIL

    context = Context(email_context)
    
    text_part = loader.get_template_from_string("%s{%% include 'helpdesk/email_text_footer.txt' %%}" % t.plain_text).render(context)
    html_part = loader.get_template_from_string("{%% extends 'helpdesk/email_html_base.html' %%}{%% block title %%}%s{%% endblock %%}{%% block content %%}%s{%% endblock %%}" % (t.heading, t.html)).render(context)
    subject_part = loader.get_template_from_string("{{ ticket.ticket }} {{ ticket.title }} %s" % t.subject).render(context)

    if type(recipients) != list:
        recipients = [recipients,]

    msg = EmailMultiAlternatives(subject_part, text_part, sender, recipients, bcc=bcc)
    msg.attach_alternative(html_part, "text/html")

    if files:
        if type(files) != list:
            files = [files,]

        for file in files:
            msg.attach_file(file)
    
    return msg.send(fail_silently)

    

def send_multipart_mail(template_name, email_context, subject, recipients, sender=None, bcc=None, fail_silently=False, files=None):
    """
    This function will send a multi-part e-mail with both HTML and 
    Text parts.

    template_name must NOT contain an extension. Both HTML (.html) and TEXT 
        (.txt) versions must exist, eg 'emails/public_submit' will use both 
        public_submit.html and public_submit.txt.

    email_context should be a plain python dictionary. It is applied against
        both the email messages (templates) & the subject.

    subject can be plain text or a Django template string, eg:
        New Job: {{ job.id }} {{ job.title }}

    recipients can be either a string, eg 'a@b.com' or a list, eg:
        ['a@b.com', 'c@d.com']. Type conversion is done if needed.

    sender can be an e-mail, 'Name <email>' or None. If unspecified, the 
        DEFAULT_FROM_EMAIL will be used.

    Originally posted on my blog at http://www.rossp.org/
    """
    from django.core.mail import EmailMultiAlternatives
    from django.template import loader, Context
    from django.conf import settings

    if not sender:
        sender = settings.DEFAULT_FROM_EMAIL

    context = Context(email_context)
    
    text_part = loader.get_template('%s.txt' % template_name).render(context)
    html_part = loader.get_template('%s.html' % template_name).render(context)
    subject_part = loader.get_template_from_string(subject).render(context)

    if type(recipients) != list:
        recipients = [recipients,]

    msg = EmailMultiAlternatives(subject_part, text_part, sender, recipients, bcc=bcc)
    msg.attach_alternative(html_part, "text/html")

    if files:
        if type(files) != list:
            files = [files,]

        for file in files:
            msg.attach_file(file)
    
    return msg.send(fail_silently)


def normalise_data(data, to=100):
    """
    Used for normalising data prior to graphing with Google charting API
    """
    max_value = max(data)
    if max_value > to:
        new_data = []
        for d in data:
            new_data.append(int(d/float(max_value)*to))
        data = new_data
    return data

chart_colours = ('80C65A', '990066', 'FF9900', '3399CC', 'BBCCED', '3399CC', 'FFCC33')

def line_chart(data):
    """
    'data' is a list of lists making a table.
    Row 1, columns 2-n are data headings (the time periods)
    Rows 2-n are data, with column 1 being the line labels
    """

    column_headings = data[0][1:]
    max = 0
    for row in data[1:]:
        for field in row[1:]:
            if field > max:
                max = field


    # Set width to '65px * number of months'.
    chart_url = 'http://chart.apis.google.com/chart?cht=lc&chs=%sx90&chd=t:' % (len(column_headings)*65)
    first_row = True
    row_headings = []
    for row in data[1:]:
        # Add data to URL, normalised to the maximum for all lines on this chart
        norm = normalise_data(row[1:], max)
        if not first_row:
            chart_url += '|'
        chart_url += ','.join([str(num) for num in norm])
        row_headings.append(row[0])
        first_row = False

    chart_url += '&chds='
    rows = len(data)-1
    first = True
    for row in range(rows):
        # Set maximum data ranges to '0:x' where 'x' is the maximum number in use.
        if not first: 
            chart_url += ','
        chart_url += '0,%s' % max
        first = False
    chart_url += '&chdl=%s' % '|'.join(row_headings) # Display legend/labels
    chart_url += '&chco=%s' % ','.join(chart_colours) # Default colour set
    chart_url += '&chxt=x,y' # Turn on axis labels
    chart_url += '&chxl=0:|%s|1:|0|%s' % ('|'.join(column_headings), max) # Axis Label Text

    return chart_url

def bar_chart(data):
    """
    'data' is a list of lists making a table.
    Row 1, columns 2-n are data headings
    Rows 2-n are data, with column 1 being the line labels
    """

    column_headings = data[0][1:]
    max = 0
    for row in data[1:]:
        for field in row[1:]:
            if field > max:
                max = field


    # Set width to '150px * number of months'.
    chart_url = 'http://chart.apis.google.com/chart?cht=bvg&chs=%sx90&chd=t:' % (len(column_headings) * 150)
    first_row = True
    row_headings = []
    for row in data[1:]:
        # Add data to URL, normalised to the maximum for all lines on this chart
        norm = normalise_data(row[1:], max)
        if not first_row:
            chart_url += '|'
        chart_url += ','.join([str(num) for num in norm])
        row_headings.append(row[0])
        first_row = False

    chart_url += '&chds=0,%s' % max
    chart_url += '&chdl=%s' % '|'.join(row_headings) # Display legend/labels
    chart_url += '&chco=%s' % ','.join(chart_colours) # Default colour set
    chart_url += '&chxt=x,y' # Turn on axis labels
    chart_url += '&chxl=0:|%s|1:|0|%s' % ('|'.join(column_headings), max) # Axis Label Text

    return chart_url

def query_to_dict(results, descriptions):
    """ Replacement method for cursor.dictfetchall() as that method no longer
    exists in psycopg2, and I'm guessing in other backends too.
    
    Converts the results of a raw SQL query into a list of dictionaries, suitable 
    for use in templates etc. """
    output = []
    for data in results:
        row = {}
        i = 0
        for column in descriptions:
            row[column[0]] = data[i]
            i += 1

        output.append(row)
    return output
