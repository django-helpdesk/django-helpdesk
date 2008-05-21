"""
Jutda Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/staff.py - The bulk of the application - provides most business logic and 
                 renders all staff-facing views.
"""
from datetime import datetime

from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import loader, Context, RequestContext
from django.utils.translation import ugettext as _

from helpdesk.forms import TicketForm
from helpdesk.lib import send_templated_mail, line_chart, bar_chart, query_to_dict
from helpdesk.models import Ticket, Queue, FollowUp, TicketChange, PreSetReply, Attachment

def dashboard(request):
    """
    A quick summary overview for users: A list of their own tickets, a table
    showing ticket counts by queue/status, and a list of unassigned tickets 
    with options for them to 'Take' ownership of said tickets.
    """

    tickets = Ticket.objects.filter(assigned_to=request.user).exclude(status=Ticket.CLOSED_STATUS)
    unassigned_tickets = Ticket.objects.filter(assigned_to__isnull=True).exclude(status=Ticket.CLOSED_STATUS)

    from django.db import connection
    cursor = connection.cursor()
    cursor.execute("""
        SELECT      q.id as queue,
                    q.title AS name,
                    COUNT(CASE t.status WHEN '1' THEN t.id WHEN '2' THEN t.id END) AS open,
                    COUNT(CASE t.status WHEN '3' THEN t.id END) AS resolved
            FROM    helpdesk_ticket t,
                    helpdesk_queue q
            WHERE   q.id =  t.queue_id
            GROUP BY queue, name
            ORDER BY q.id;
    """)
    dash_tickets = query_to_dict(cursor.fetchall(), cursor.description)

    return render_to_response('helpdesk/dashboard.html',
        RequestContext(request, {
            'user_tickets': tickets,
            'unassigned_tickets': unassigned_tickets,
            'dash_tickets': dash_tickets,
        }))
dashboard = login_required(dashboard)

def delete_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    if request.method == 'GET':
        return render_to_response('helpdesk/delete_ticket.html',
            RequestContext(request, {
                'ticket': ticket,
            }))
    else:
        ticket.delete()
        return HttpResponseRedirect(reverse('helpdesk_home'))
delete_ticket = login_required(delete_ticket)

def view_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.GET.has_key('take'):
        ticket.assigned_to = request.user
        ticket.save()

    if request.GET.has_key('close') and ticket.status == Ticket.RESOLVED_STATUS:
        if not ticket.assigned_to: 
            owner = 0
        else:
            owner = ticket.assigned_to.id
        request.POST = {'new_status': Ticket.CLOSED_STATUS, 'public': 1, 'owner': owner, 'title': ticket.title, 'comment': _('Accepted resolution and closed ticket')}
        return update_ticket(request, ticket_id)

    return render_to_response('helpdesk/ticket.html',
        RequestContext(request, {
            'ticket': ticket,
            'active_users': User.objects.filter(is_active=True),
            'priorities': Ticket.PRIORITY_CHOICES,
            'preset_replies': PreSetReply.objects.filter(Q(queues=ticket.queue) | Q(queues__isnull=True)),
        }))
view_ticket = login_required(view_ticket)

def update_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    comment = request.POST.get('comment', '')
    new_status = int(request.POST.get('new_status', ticket.status))
    title = request.POST.get('title', '')
    public = request.POST.get('public', False)
    owner = int(request.POST.get('owner', None))
    priority = int(request.POST.get('priority', ticket.priority))
    
    if not owner and ticket.assigned_to:
        owner = ticket.assigned_to.id

    f = FollowUp(ticket=ticket, date=datetime.now(), comment=comment, user=request.user)
    if public:
        f.public = True

    reassigned = False

    if owner:
        if owner != 0 and (ticket.assigned_to and owner != ticket.assigned_to.id) or not ticket.assigned_to:
            new_user = User.objects.get(id=owner)
            f.title = _('Assigned to %(username)s') % {'username': new_user.username}
            ticket.assigned_to = new_user
            reassigned = True
        else:
            f.title = _('Unassigned')
            ticket.assigned_to = None
    
    if new_status != ticket.status:
        ticket.status = new_status
        ticket.save()
        f.new_status = new_status
        if f.title:
            f.title += ' and %s' % ticket.get_status_display()
        else:
            f.title = '%s' % ticket.get_status_display()

    if not f.title:
        if f.comment:
            f.title = _('Comment')
        else:
            f.title = _('Updated')

    f.save()
    
    if title != ticket.title:
        c = TicketChange(followup=f, field=_('Title'), old_value=ticket.title, new_value=title)
        c.save()
        ticket.title = title

    if priority != ticket.priority:
        c = TicketChange(followup=f, field=_('Priority'), old_value=ticket.priority, new_value=priority)
        c.save()
        ticket.priority = priority

    if f.new_status == Ticket.RESOLVED_STATUS:
        ticket.resolution = comment
    
    if ticket.submitter_email and ((f.comment != '' and public) or (f.new_status in (Ticket.RESOLVED_STATUS, Ticket.CLOSED_STATUS))):
        context = {
            'ticket': ticket,
            'queue': ticket.queue,
            'resolution': ticket.resolution,
            'comment': f.comment,
        }
        if f.new_status == Ticket.RESOLVED_STATUS:
            template = 'resolved_submitter'
        elif f.new_status == Ticket.CLOSED_STATUS:
            template = 'closed_submitter'
        else:
            template = 'updated_submitter'
        send_templated_mail(template, context, recipients=ticket.submitter_email, sender=ticket.queue.from_address, fail_silently=True)

    if ticket.assigned_to and request.user != ticket.assigned_to and ticket.assigned_to.email:
        # We only send e-mails to staff members if the ticket is updated by 
        # another user.
        if reassigned:
            template_staff = 'assigned_owner'
        elif f.new_status == Ticket.RESOLVED_STATUS:
            template_staff = 'resolved_owner'
        elif f.new_status == Ticket.CLOSED_STATUS:
            template_staff = 'closed_owner'
        else:
            template_staff = 'updated_owner'
        
        send_templated_mail(template_staff, context, recipients=ticket.assigned_to.email, sender=ticket.queue.from_address, fail_silently=True)
            
    if ticket.queue.updated_ticket_cc:
        if reassigned:
            template_cc = 'assigned_cc'
        elif f.new_status == Ticket.RESOLVED_STATUS:
            template_cc = 'resolved_cc'
        elif f.new_status == Ticket.CLOSED_STATUS:
            template_cc = 'closed_cc'
        else:
            template_cc = 'updated_cc'
        
        send_templated_mail(template_cc, context, recipients=ticket.queue.updated_ticket_cc, sender=ticket.queue.from_address, fail_silently=True)

    if request.FILES:
        for file in request.FILES.getlist('attachment'):
            filename = file['filename'].replace(' ', '_')
            a = Attachment(followup=f, filename=filename, mime_type=file['content-type'], size=len(file['content']))
            a.save_file_file(file['filename'], file['content'])
            a.save()

    ticket.save()
            
    return HttpResponseRedirect(ticket.get_absolute_url())
update_ticket = login_required(update_ticket)

def ticket_list(request):
    tickets = Ticket.objects.select_related()
    context = {}

    ### FILTERING
    queues = request.GET.getlist('queue')
    if queues:
        queues = [int(q) for q in queues]
        tickets = tickets.filter(queue__id__in=queues)
        context = dict(context, queues=queues)

    owners = request.GET.getlist('assigned_to')
    if owners:
        owners = [int(u) for u in owners]
        tickets = tickets.filter(assigned_to__id__in=owners)
        context = dict(context, owners=owners)

    statuses = request.GET.getlist('status')
    if statuses:
        statuses = [int(s) for s in statuses]
        tickets = tickets.filter(status__in=statuses)
        context = dict(context, statuses=statuses)

    ### KEYWORD SEARCHING
    q = request.GET.get('q', None)
    
    if q:
        qset = (
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(resolution__icontains=q) |
            Q(submitter_email__icontains=q)
        )
        tickets = tickets.filter(qset)
        context = dict(context, query=q)
   
    ### SORTING
    sort = request.GET.get('sort', None)
    if sort not in ('status', 'assigned_to', 'created', 'title', 'queue', 'priority'):
        sort = 'created'
    tickets = tickets.order_by(sort)
    context = dict(context, sort=sort)

    return render_to_response('helpdesk/ticket_list.html',
        RequestContext(request, dict(
            context,
            tickets=tickets,
            user_choices=User.objects.filter(is_active=True),
            queue_choices=Queue.objects.all(),
            status_choices=Ticket.STATUS_CHOICES,
        )))
ticket_list = login_required(ticket_list)

def create_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        form.fields['queue'].choices = [('', '--------')] + [[q.id, q.title] for q in Queue.objects.all()]
        form.fields['assigned_to'].choices = [('', '--------')] + [[u.id, u.username] for u in User.objects.filter(is_active=True)]
        if form.is_valid():
            ticket = form.save(user=request.user)
            return HttpResponseRedirect(ticket.get_absolute_url())
    else:
        form = TicketForm()
        form.fields['queue'].choices = [('', '--------')] + [[q.id, q.title] for q in Queue.objects.all()]
        form.fields['assigned_to'].choices = [('', '--------')] + [[u.id, u.username] for u in User.objects.filter(is_active=True)]

    return render_to_response('helpdesk/create_ticket.html', 
        RequestContext(request, {
            'form': form,
        }))
create_ticket = login_required(create_ticket)

def raw_details(request, type):
    if not type in ('preset',):
        raise Http404
    
    if type == 'preset' and request.GET.get('id', False):
        try:
            preset = PreSetReply.objects.get(id=request.GET.get('id'))
            return HttpResponse(preset.body)
        except PreSetReply.DoesNotExist:
            raise Http404
    
    raise Http404
raw_details = login_required(raw_details)

def hold_ticket(request, ticket_id, unhold=False):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if unhold:
        ticket.on_hold = False
        title = _('Ticket taken off hold')
    else:
        ticket.on_hold = True
        title = _('Ticket placed on hold')
    
    f = FollowUp(
        ticket = ticket,
        user = request.user,
        title = title,
        date = datetime.now(),
        public = True,
    )
    f.save()
    
    ticket.save()
    
    return HttpResponseRedirect(ticket.get_absolute_url())
hold_ticket = login_required(hold_ticket)

def unhold_ticket(request, ticket_id):
    return hold_ticket(request, ticket_id, unhold=True)
unhold_ticket = login_required(unhold_ticket)

def rss_list(request):
    return render_to_response('helpdesk/rss_list.html', 
        RequestContext(request, {
            'queues': Queue.objects.all(),
        }))
rss_list = login_required(rss_list)

def report_index(request):
    return render_to_response('helpdesk/report_index.html',
        RequestContext(request, {}))
report_index = login_required(report_index)

def run_report(request, report):
    priority_sql = []
    priority_columns = []
    for p in Ticket.PRIORITY_CHOICES:
        priority_sql.append("COUNT(CASE t.priority WHEN '%s' THEN t.id END) AS \"%s\"" % (p[0], p[1]._proxy____unicode_cast()))
        priority_columns.append("%s" % p[1]._proxy____unicode_cast())
    priority_sql = ", ".join(priority_sql)
    
    status_sql = []
    status_columns = []
    for s in Ticket.STATUS_CHOICES:
        status_sql.append("COUNT(CASE t.status WHEN '%s' THEN t.id END) AS \"%s\"" % (s[0], s[1]._proxy____unicode_cast()))
        status_columns.append("%s" % s[1]._proxy____unicode_cast())
    status_sql = ", ".join(status_sql)
    
    queue_sql = []
    queue_columns = []
    for q in Queue.objects.all():
        queue_sql.append("COUNT(CASE t.queue_id WHEN '%s' THEN t.id END) AS \"%s\"" % (q.id, q.title))
        queue_columns.append(q.title)
    queue_sql = ", ".join(queue_sql)

    month_sql = []
    months = (
        'Jan',
        'Feb',
        'Mar',
        'Apr',
        'May',
        'Jun',
        'Jul',
        'Aug',
        'Sep',
        'Oct',
        'Nov',
        'Dec',
    )
    month_columns = []
    
    first_ticket = Ticket.objects.all().order_by('created')[0]
    first_month = first_ticket.created.month
    first_year = first_ticket.created.year
    
    last_ticket = Ticket.objects.all().order_by('-created')[0]
    last_month = last_ticket.created.month
    last_year = last_ticket.created.year

    periods = []
    year, month = first_year, first_month
    working = True

    while working:
        periods.append((year, month))
        month += 1
        if month > 12:
            year += 1
            month = 1
        if month > last_month and year >= last_year:
            working = False



    for (year, month) in periods:
        sqlmonth = '%s-%s' % (year, months[month-1])
        desc = '%s %s' % (months[month-1], year)
        month_sql.append("COUNT(CASE to_char(t.created, 'YYYY-Mon') WHEN '%s' THEN t.id END) AS \"%s\"" % (sqlmonth, desc))
        month_columns.append(desc)
    month_sql = ", ".join(month_sql)

    queue_base_sql = """
            SELECT      q.title as queue, %s
                FROM    helpdesk_ticket t,
                        helpdesk_queue q
                WHERE   q.id =  t.queue_id
                GROUP BY queue
                ORDER BY queue;
                """

    user_base_sql = """
            SELECT      u.username as username, %s
                FROM    helpdesk_ticket t,
                        auth_user u
                WHERE   u.id =  t.assigned_to_id
                GROUP BY u.username
                ORDER BY u.username;
                """

    if report == 'userpriority':
        sql = user_base_sql % priority_sql
        columns = ['username'] + priority_columns
    
    elif report == 'userqueue':
        sql = user_base_sql % queue_sql
        columns = ['username'] + queue_columns
    
    elif report == 'userstatus':
        sql = user_base_sql % status_sql
        columns = ['username'] + status_columns
    
    elif report == 'usermonth':
        sql = user_base_sql % month_sql
        columns = ['username'] + month_columns
    
    elif report == 'queuepriority':
        sql = queue_base_sql % priority_sql
        columns = ['queue'] + priority_columns
    
    elif report == 'queuestatus':
        sql = queue_base_sql % status_sql
        columns = ['queue'] + status_columns
    
    elif report == 'queuemonth':
        sql = queue_base_sql % month_sql
        columns = ['queue'] + month_columns


    from django.db import connection
    cursor = connection.cursor()
    cursor.execute(sql)
    report_output = query_to_dict(cursor.fetchall(), cursor.description)

    data = []

    for record in report_output:
        line = []
        for c in columns:
            line.append(record[c])
        data.append(line)

    if report in ('queuemonth', 'usermonth'):
        chart_url = line_chart([columns] + data)
    elif report in ('queuestatus', 'queuepriority', 'userstatus', 'userpriority'):
        chart_url = bar_chart([columns] + data)
    else:
        chart_url = ''
    
    return render_to_response('helpdesk/report_output.html',
        RequestContext(request, {
            'headings': columns,
            'data': data,
            'sql': sql,
            'chart': chart_url,
        }))
run_report = login_required(run_report)
