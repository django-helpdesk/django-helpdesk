"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/staff.py - The bulk of the application - provides most business logic and
                 renders all staff-facing views.
"""

from datetime import datetime
import sys

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.core import paginator
from django.db import connection
from django.db.models import Q
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import loader, Context, RequestContext
from django.utils.translation import ugettext as _
from django.utils.html import escape
from django import forms

from helpdesk.forms import TicketForm, UserSettingsForm, EmailIgnoreForm, EditTicketForm, TicketCCForm, EditFollowUpForm, TicketDependencyForm
from helpdesk.lib import send_templated_mail, query_to_dict, apply_query, safe_template_context
from helpdesk.models import Ticket, Queue, FollowUp, TicketChange, PreSetReply, Attachment, SavedSearch, IgnoreEmail, TicketCC, TicketDependency
from helpdesk.settings import HAS_TAG_SUPPORT
from helpdesk import settings as helpdesk_settings
  
if HAS_TAG_SUPPORT:
    from tagging.models import Tag, TaggedItem

if helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE:
    # treat 'normal' users like 'staff'
    staff_member_required = user_passes_test(lambda u: u.is_authenticated() and u.is_active)
else:
    staff_member_required = user_passes_test(lambda u: u.is_authenticated() and u.is_active and u.is_staff)


superuser_required = user_passes_test(lambda u: u.is_authenticated() and u.is_active and u.is_superuser)


def dashboard(request):
    """
    A quick summary overview for users: A list of their own tickets, a table
    showing ticket counts by queue/status, and a list of unassigned tickets
    with options for them to 'Take' ownership of said tickets.
    """

    # open & reopened tickets, assigned to current user
    tickets = Ticket.objects.filter(
            assigned_to=request.user,
        ).exclude(
            status__in = [Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS],
        )

    # closed & resolved tickets, assigned to current user
    tickets_closed_resolved =  Ticket.objects.filter(
            assigned_to=request.user, 
            status__in = [Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS])

    unassigned_tickets = Ticket.objects.filter(
            assigned_to__isnull=True,
        ).exclude(
            status=Ticket.CLOSED_STATUS,
        )

    # all tickets, reported by current user
    all_tickets_reported_by_current_user = ''
    email_current_user = request.user.email
    if email_current_user:
        all_tickets_reported_by_current_user = Ticket.objects.filter(
            submitter_email=email_current_user,
        ).order_by('status')


    # The following query builds a grid of queues & ticket statuses,
    # to be displayed to the user. EG:
    #          Open  Resolved
    # Queue 1    10     4
    # Queue 2     4    12

    cursor = connection.cursor()
    if helpdesk_settings.HELPDESK_DASHBOARD_HIDE_EMPTY_QUEUES:
        cursor.execute("""
            SELECT      q.id as queue,
                        q.title AS name,
                        COUNT(CASE t.status WHEN '1' THEN t.id WHEN '2' THEN t.id END) AS open,
                        COUNT(CASE t.status WHEN '3' THEN t.id END) AS resolved,
                        COUNT(CASE t.status WHEN '4' THEN t.id END) AS closed
                FROM    helpdesk_ticket t,
                        helpdesk_queue q
                WHERE   q.id = t.queue_id
                GROUP BY queue, name
                ORDER BY q.id;
        """)
    else:
        cursor.execute("""
            SELECT      q.id as queue,
                        q.title AS name,
                        COUNT(CASE t.status WHEN '1' THEN t.id WHEN '2' THEN t.id END) AS open,
                        COUNT(CASE t.status WHEN '3' THEN t.id END) AS resolved,
                        COUNT(CASE t.status WHEN '4' THEN t.id END) AS closed
                FROM    helpdesk_queue q
                LEFT OUTER JOIN helpdesk_ticket t
                ON      q.id = t.queue_id            
                GROUP BY queue, name
                ORDER BY q.id;
        """)    
    
    
    dash_tickets = query_to_dict(cursor.fetchall(), cursor.description)

    return render_to_response('helpdesk/dashboard.html',
        RequestContext(request, {
            'user_tickets': tickets,
            'user_tickets_closed_resolved': tickets_closed_resolved,
            'unassigned_tickets': unassigned_tickets,
            'all_tickets_reported_by_current_user': all_tickets_reported_by_current_user,
            'dash_tickets': dash_tickets,
        }))
dashboard = staff_member_required(dashboard)


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
delete_ticket = staff_member_required(delete_ticket)

def followup_edit(request, ticket_id, followup_id, ):
    "Edit followup options with an ability to change the ticket."
    followup = get_object_or_404(FollowUp, id=followup_id)
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.method == 'GET':
        form = EditFollowUpForm(initial=
                                     {'title': escape(followup.title),
                                      'ticket': followup.ticket,
                                      'comment': escape(followup.comment),
                                      'public': followup.public,
                                      'new_status': followup.new_status,
                                      })
        
        return render_to_response('helpdesk/followup_edit.html',
            RequestContext(request, {
                'followup': followup,
                'ticket': ticket,
                'form': form,
        }))
    elif request.method == 'POST':
        form = EditFollowUpForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            _ticket = form.cleaned_data['ticket']
            comment = form.cleaned_data['comment']
            public = form.cleaned_data['public']
            new_status = form.cleaned_data['new_status']
            #will save previous date
            old_date = followup.date
            new_followup = FollowUp(title=title, date=old_date, ticket=_ticket, comment=comment, public=public, new_status=new_status, )
            # keep old user if one did exist before.
            if followup.user:
                new_followup.user = followup.user
            new_followup.save()
            # get list of old attachments & link them to new_followup
            attachments = Attachment.objects.filter(followup = followup)            
            for attachment in attachments:
                attachment.followup = new_followup
                attachment.save()
            # delete old followup
            followup.delete()                
        return HttpResponseRedirect(reverse('helpdesk_view', args=[ticket.id]))
            
def view_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.GET.has_key('take'):
        # Allow the user to assign the ticket to themselves whilst viewing it.
        
        # Trick the update_ticket() view into thinking it's being called with
        # a valid POST.
        request.POST = {
            'owner': request.user.id,
            'public': 1,
            'title': ticket.title,
            'comment': ''
        }
        return update_ticket(request, ticket_id)

    if request.GET.has_key('close') and ticket.status == Ticket.RESOLVED_STATUS:
        if not ticket.assigned_to:
            owner = 0
        else:
            owner = ticket.assigned_to.id

        # Trick the update_ticket() view into thinking it's being called with
        # a valid POST.
        request.POST = {
            'new_status': Ticket.CLOSED_STATUS,
            'public': 1,
            'owner': owner,
            'title': ticket.title,
            'comment': _('Accepted resolution and closed ticket'),
            }

        return update_ticket(request, ticket_id)

    if helpdesk_settings.HELPDESK_STAFF_ONLY_TICKET_OWNERS:
        users = User.objects.filter(is_active=True, is_staff=True).order_by('username')
    else:
        users = User.objects.filter(is_active=True).order_by('username')


    # TODO: shouldn't this template get a form to begin with?
    form = TicketForm(initial={'due_date':ticket.due_date})

    return render_to_response('helpdesk/ticket.html',
        RequestContext(request, {
            'ticket': ticket,
            'form': form,
            'active_users': users,
            'priorities': Ticket.PRIORITY_CHOICES,
            'preset_replies': PreSetReply.objects.filter(Q(queues=ticket.queue) | Q(queues__isnull=True)),
            'tags_enabled': HAS_TAG_SUPPORT,
        }))
view_ticket = staff_member_required(view_ticket)


def update_ticket(request, ticket_id, public=False):
    if not (public or (request.user.is_authenticated() and request.user.is_active and (request.user.is_staff or helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE))):
        return HttpResponseForbidden(_('Sorry, you need to login to do that.'))

    ticket = get_object_or_404(Ticket, id=ticket_id)

    comment = request.POST.get('comment', '')
    new_status = int(request.POST.get('new_status', ticket.status))
    title = request.POST.get('title', '')
    public = request.POST.get('public', False)
    owner = int(request.POST.get('owner', None))
    priority = int(request.POST.get('priority', ticket.priority))
    due_date_year = request.POST.get('due_date_year', None)
    due_date_month = request.POST.get('due_date_month', None)
    due_date_day = request.POST.get('due_date_day', None)

    if not (due_date_year and due_date_month and due_date_day):
        due_date = ticket.due_date
    else:
        due_date = datetime(
                int(due_date_year),
                int(due_date_month),
                int(due_date_day))
    tags = request.POST.get('tags', '')

    # We need to allow the 'ticket' and 'queue' contexts to be applied to the
    # comment.
    from django.template import loader, Context
    context = safe_template_context(ticket)
    # this line sometimes creates problems if code is sent as a comment.
    # if comment contains some django code, like "why does {% if bla %} crash",
    # then the following line will give us a crash, since django expects {% if %}
    # to be closed with an {% endif %} tag.
    comment = loader.get_template_from_string(comment).render(Context(context))

    if owner is None and ticket.assigned_to:
        owner = ticket.assigned_to.id

    f = FollowUp(ticket=ticket, date=datetime.now(), comment=comment)

    if request.user.is_staff or helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE:
        f.user = request.user

    f.public = public

    reassigned = False

    if owner is not None:
        if owner != 0 and ((ticket.assigned_to and owner != ticket.assigned_to.id) or not ticket.assigned_to):
            new_user = User.objects.get(id=owner)
            f.title = _('Assigned to %(username)s') % {
                'username': new_user.username,
                }
            ticket.assigned_to = new_user
            reassigned = True
        # user changed owner to 'unassign'
        elif owner == 0 and ticket.assigned_to is not None:
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

    files = []
    if request.FILES:
        import mimetypes, os
        for file in request.FILES.getlist('attachment'):
            filename = file.name.replace(' ', '_')
            a = Attachment(
                followup=f,
                filename=filename,
                mime_type=mimetypes.guess_type(filename)[0] or 'application/octet-stream',
                size=file.size,
                )
            a.file.save(file.name, file, save=False)
            a.save()

            if file.size < getattr(settings, 'MAX_EMAIL_ATTACHMENT_SIZE', 512000):
                # Only files smaller than 512kb (or as defined in
                # settings.MAX_EMAIL_ATTACHMENT_SIZE) are sent via email.
                files.append(a.file.path)


    if title != ticket.title:
        c = TicketChange(
            followup=f,
            field=_('Title'),
            old_value=ticket.title,
            new_value=title,
            )
        c.save()
        ticket.title = title

    if priority != ticket.priority:
        c = TicketChange(
            followup=f,
            field=_('Priority'),
            old_value=ticket.priority,
            new_value=priority,
            )
        c.save()
        ticket.priority = priority

    if due_date != ticket.due_date:
        c = TicketChange(
            followup=f,
            field=_('Due on'),
            old_value=ticket.due_date,
            new_value=due_date,
            )
        c.save()
        ticket.due_date = due_date

    if HAS_TAG_SUPPORT:
        if tags != ticket.tags:
            c = TicketChange(
                followup=f,
                field=_('Tags'),
                old_value=ticket.tags,
                new_value=tags,
                )
            c.save()
            ticket.tags = tags

    if new_status in [ Ticket.RESOLVED_STATUS, Ticket.CLOSED_STATUS ]:
        ticket.resolution = comment

    messages_sent_to = []

    # ticket might have changed above, so we re-instantiate context with the 
    # (possibly) updated ticket.
    context = safe_template_context(ticket)
    context.update(
        resolution=ticket.resolution,
        comment=f.comment,
        )

    if ticket.submitter_email and public and (f.comment or (f.new_status in (Ticket.RESOLVED_STATUS, Ticket.CLOSED_STATUS))):

        if f.new_status == Ticket.RESOLVED_STATUS:
            template = 'resolved_submitter'
        elif f.new_status == Ticket.CLOSED_STATUS:
            template = 'closed_submitter'
        else:
            template = 'updated_submitter'

        send_templated_mail(
            template,
            context,
            recipients=ticket.submitter_email,
            sender=ticket.queue.from_address,
            fail_silently=True,
            files=files,
            )
        messages_sent_to.append(ticket.submitter_email)

        for cc in ticket.ticketcc_set.all():
            if cc.email_address not in messages_sent_to:
                send_templated_mail(
                    template,
                    context,
                    recipients=cc.email_address,
                    sender=ticket.queue.from_address,
                    fail_silently=True,
                    )
                messages_sent_to.append(cc.email_address)

    if ticket.assigned_to and request.user != ticket.assigned_to and ticket.assigned_to.email and ticket.assigned_to.email not in messages_sent_to:
        # We only send e-mails to staff members if the ticket is updated by
        # another user. The actual template varies, depending on what has been
        # changed.
        if reassigned:
            template_staff = 'assigned_owner'
        elif f.new_status == Ticket.RESOLVED_STATUS:
            template_staff = 'resolved_owner'
        elif f.new_status == Ticket.CLOSED_STATUS:
            template_staff = 'closed_owner'
        else:
            template_staff = 'updated_owner'

        if (not reassigned or ( reassigned and ticket.assigned_to.usersettings.settings.get('email_on_ticket_assign', False))) or (not reassigned and ticket.assigned_to.usersettings.settings.get('email_on_ticket_change', False)):
            send_templated_mail(
                template_staff,
                context,
                recipients=ticket.assigned_to.email,
                sender=ticket.queue.from_address,
                fail_silently=True,
                files=files,
                )
            messages_sent_to.append(ticket.assigned_to.email)

    if ticket.queue.updated_ticket_cc and ticket.queue.updated_ticket_cc not in messages_sent_to:
        if reassigned:
            template_cc = 'assigned_cc'
        elif f.new_status == Ticket.RESOLVED_STATUS:
            template_cc = 'resolved_cc'
        elif f.new_status == Ticket.CLOSED_STATUS:
            template_cc = 'closed_cc'
        else:
            template_cc = 'updated_cc'

        send_templated_mail(
            template_cc,
            context,
            recipients=ticket.queue.updated_ticket_cc,
            sender=ticket.queue.from_address,
            fail_silently=True,
            files=files,
            )

    ticket.save()

    if request.user.is_staff or helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE:
        return HttpResponseRedirect(ticket.get_absolute_url())
    else:
        return HttpResponseRedirect(ticket.ticket_url)


def mass_update(request):
    tickets = request.POST.getlist('ticket_id')
    action = request.POST.get('action', None)
    if not (tickets and action):
        return HttpResponseRedirect(reverse('helpdesk_list'))

    if action.startswith('assign_'):
        parts = action.split('_')
        user = User.objects.get(id=parts[1])
        action = 'assign'
    elif action == 'take':
        user = request.user
        action = 'assign'

    for t in Ticket.objects.filter(id__in=tickets):
        if action == 'assign' and t.assigned_to != user:
            t.assigned_to = user
            t.save()
            f = FollowUp(ticket=t, date=datetime.now(), title=_('Assigned to %(username)s in bulk update' % {'username': user.username}), public=True, user=request.user)
            f.save()
        elif action == 'unassign' and t.assigned_to is not None:
            t.assigned_to = None
            t.save()
            f = FollowUp(ticket=t, date=datetime.now(), title=_('Unassigned in bulk update'), public=True, user=request.user)
            f.save()
        elif action == 'close' and t.status != Ticket.CLOSED_STATUS:
            t.status = Ticket.CLOSED_STATUS
            t.save()
            f = FollowUp(ticket=t, date=datetime.now(), title=_('Closed in bulk update'), public=False, user=request.user, new_status=Ticket.CLOSED_STATUS)
            f.save()
        elif action == 'close_public' and t.status != Ticket.CLOSED_STATUS:
            t.status = Ticket.CLOSED_STATUS
            t.save()
            f = FollowUp(ticket=t, date=datetime.now(), title=_('Closed in bulk update'), public=True, user=request.user, new_status=Ticket.CLOSED_STATUS)
            f.save()
            # Send email to Submitter, Owner, Queue CC
            context = safe_template_context(t)
            context.update(
                resolution = t.resolution,
                queue = t.queue,
                )

            messages_sent_to = []

            if t.submitter_email:
                send_templated_mail(
                    'closed_submitter',
                    context,
                    recipients=t.submitter_email,
                    sender=t.queue.from_address,
                    fail_silently=True,
                    )
                messages_sent_to.append(t.submitter_email)

            for cc in t.ticketcc_set.all():
                if cc.email_address not in messages_sent_to:
                    send_templated_mail(
                        'closed_submitter',
                        context,
                        recipients=cc.email_address,
                        sender=t.queue.from_address,
                        fail_silently=True,
                        )
                    messages_sent_to.append(cc.email_address)

            if t.assigned_to and request.user != t.assigned_to and t.assigned_to.email and t.assigned_to.email not in messages_sent_to:
                send_templated_mail(
                    'closed_owner',
                    context,
                    recipients=t.assigned_to.email,
                    sender=t.queue.from_address,
                    fail_silently=True,
                    )
                messages_sent_to.append(t.assigned_to.email)

            if t.queue.updated_ticket_cc and t.queue.updated_ticket_cc not in messages_sent_to:
                send_templated_mail(
                    'closed_cc',
                    context,
                    recipients=t.queue.updated_ticket_cc,
                    sender=t.queue.from_address,
                    fail_silently=True,
                    )

        elif action == 'delete':
            t.delete()

    return HttpResponseRedirect(reverse('helpdesk_list'))
mass_update = staff_member_required(mass_update)

def ticket_list(request):
    context = {}

    # Query_params will hold a dictionary of paramaters relating to
    # a query, to be saved if needed:
    query_params = {
        'filtering': {},
        'sorting': None,
        'sortreverse': False,
        'keyword': None,
        'other_filter': None,
        }

    from_saved_query = False

    # If the user is coming from the header/navigation search box, lets' first
    # look at their query to see if they have entered a valid ticket number. If
    # they have, just redirect to that ticket number. Otherwise, we treat it as
    # a keyword search.

    if request.GET.get('search_type', None) == 'header':
        query = request.GET.get('q')
        filter = None
        if query.find('-') > 0:
            queue, id = query.split('-')
            try:
                id = int(id)
            except ValueError:
                id = None

            if id:
                filter = {'queue__slug': queue, 'id': id }
        else:
            try:
                query = int(query)
            except ValueError:
                query = None

            if query:
                filter = {'id': int(query) }

        if filter:
            try:
                ticket = Ticket.objects.get(**filter)
                return HttpResponseRedirect(ticket.staff_url)
            except Ticket.DoesNotExist:
                # Go on to standard keyword searching
                pass

    saved_query = None
    if request.GET.get('saved_query', None):
        from_saved_query = True
        try:
            saved_query = SavedSearch.objects.get(pk=request.GET.get('saved_query'))
        except SavedSearch.DoesNotExist:
            return HttpResponseRedirect(reverse('helpdesk_list'))
        if not (saved_query.shared or saved_query.user == request.user):
            return HttpResponseRedirect(reverse('helpdesk_list'))

        import cPickle
        from helpdesk.lib import b64decode
        query_params = cPickle.loads(b64decode(str(saved_query.query)))
    elif not (  request.GET.has_key('queue')
            or  request.GET.has_key('assigned_to')
            or  request.GET.has_key('status')
            or  request.GET.has_key('q')
            or  request.GET.has_key('sort')
            or  request.GET.has_key('sortreverse') 
            or  request.GET.has_key('tags') ):

        # Fall-back if no querying is being done, force the list to only
        # show open/reopened/resolved (not closed) cases sorted by creation
        # date.

        query_params = {
            'filtering': {'status__in': [1, 2, 3]},
            'sorting': 'created',
        }
    else:
        queues = request.GET.getlist('queue')
        if queues:
            try:
                queues = [int(q) for q in queues]
                query_params['filtering']['queue__id__in'] = queues
            except ValueError:
                pass

        owners = request.GET.getlist('assigned_to')
        if owners:
            try:
                owners = [int(u) for u in owners]
                query_params['filtering']['assigned_to__id__in'] = owners
            except ValueError:
                pass

        statuses = request.GET.getlist('status')
        if statuses:
            try:
                statuses = [int(s) for s in statuses]
                query_params['filtering']['status__in'] = statuses
            except ValueError:
                pass

        date_from = request.GET.get('date_from')
        if date_from:
            query_params['filtering']['created__gte'] = date_from
        
        date_to = request.GET.get('date_to')
        if date_to:
            query_params['filtering']['created__lte'] = date_to

        ### KEYWORD SEARCHING
        q = request.GET.get('q', None)

        if q:
            qset = (
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(resolution__icontains=q) |
                Q(submitter_email__icontains=q)
            )
            context = dict(context, query=q)

            query_params['other_filter'] = qset

        ### SORTING
        sort = request.GET.get('sort', None)
        if sort not in ('status', 'assigned_to', 'created', 'title', 'queue', 'priority'):
            sort = 'created'
        query_params['sorting'] = sort

        sortreverse = request.GET.get('sortreverse', None)
        query_params['sortreverse'] = sortreverse

    try:
        ticket_qs = apply_query(Ticket.objects.select_related(), query_params)
    except ValidationError:
        # invalid parameters in query, return default query
        query_params = {
            'filtering': {'status__in': [1, 2, 3]},
            'sorting': 'created',
        }
        ticket_qs = apply_query(Ticket.objects.select_related(), query_params)

    ## TAG MATCHING
    if HAS_TAG_SUPPORT:
        tags = request.GET.getlist('tags')
        if tags:
            ticket_qs = TaggedItem.objects.get_by_model(ticket_qs, tags)
            query_params['tags'] = tags

    ticket_paginator = paginator.Paginator(ticket_qs, request.user.usersettings.settings.get('tickets_per_page') or 20)
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
         page = 1

    try:
        tickets = ticket_paginator.page(page)
    except (paginator.EmptyPage, paginator.InvalidPage):
        tickets = ticket_paginator.page(ticket_paginator.num_pages)

    search_message = ''
    if context.has_key('query') and settings.DATABASE_ENGINE.startswith('sqlite'):
        search_message = _('<p><strong>Note:</strong> Your keyword search is case sensitive because of your database. This means the search will <strong>not</strong> be accurate. By switching to a different database system you will gain better searching! For more information, read the <a href="http://docs.djangoproject.com/en/dev/ref/databases/#sqlite-string-matching">Django Documentation on string matching in SQLite</a>.')


    import cPickle
    from helpdesk.lib import b64encode
    urlsafe_query = b64encode(cPickle.dumps(query_params))

    user_saved_queries = SavedSearch.objects.filter(Q(user=request.user) | Q(shared__exact=True))

    query_string = []
    for get_key, get_value in request.GET.iteritems():
        if get_key != "page":
            query_string.append("%s=%s" % (get_key, get_value))

    tag_choices = [] 
    if HAS_TAG_SUPPORT:
        # FIXME: restrict this to tags that are actually in use
        tag_choices = Tag.objects.all()

    return render_to_response('helpdesk/ticket_list.html',
        RequestContext(request, dict(
            context,
            query_string="&".join(query_string),
            tickets=tickets,
            user_choices=User.objects.filter(is_active=True),
            queue_choices=Queue.objects.all(),
            status_choices=Ticket.STATUS_CHOICES,
            tag_choices=tag_choices,
            urlsafe_query=urlsafe_query,
            user_saved_queries=user_saved_queries,
            query_params=query_params,
            from_saved_query=from_saved_query,
            saved_query=saved_query,
            search_message=search_message,
            tags_enabled=HAS_TAG_SUPPORT
        )))
ticket_list = staff_member_required(ticket_list)


def edit_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.method == 'POST':
        form = EditTicketForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket = form.save()
            return HttpResponseRedirect(ticket.get_absolute_url())
    else:
        form = EditTicketForm(instance=ticket)
    
    return render_to_response('helpdesk/edit_ticket.html',
        RequestContext(request, {
            'form': form,
            'tags_enabled': HAS_TAG_SUPPORT,
        }))
edit_ticket = staff_member_required(edit_ticket)

def create_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST, request.FILES)
        form.fields['queue'].choices = [('', '--------')] + [[q.id, q.title] for q in Queue.objects.all()]
        form.fields['assigned_to'].choices = [('', '--------')] + [[u.id, u.username] for u in User.objects.filter(is_active=True).order_by('username')]
        if form.is_valid():
            ticket = form.save(user=request.user)
            return HttpResponseRedirect(ticket.get_absolute_url())
    else:
        initial_data = {}
        if request.user.usersettings.settings.get('use_email_as_submitter', False) and request.user.email:
            initial_data['submitter_email'] = request.user.email
        if request.GET.has_key('queue'):
            initial_data['queue'] = request.GET['queue']

        form = TicketForm(initial=initial_data)
        form.fields['queue'].choices = [('', '--------')] + [[q.id, q.title] for q in Queue.objects.all()]
        if helpdesk_settings.HELPDESK_STAFF_ONLY_TICKET_OWNERS:
            users = User.objects.filter(is_active=True, is_staff=True).order_by('username')
        else:
            users = User.objects.filter(is_active=True).order_by('username')
        form.fields['assigned_to'].choices = [('', '--------')] + [[u.id, u.username] for u in users]
        if helpdesk_settings.HELPDESK_CREATE_TICKET_HIDE_ASSIGNED_TO:
            form.fields['assigned_to'].widget = forms.HiddenInput()

    return render_to_response('helpdesk/create_ticket.html',
        RequestContext(request, {
            'form': form,
            'tags_enabled': HAS_TAG_SUPPORT,
        }))
create_ticket = staff_member_required(create_ticket)


def raw_details(request, type):
    # TODO: This currently only supports spewing out 'PreSetReply' objects,
    # in the future it needs to be expanded to include other items. All it
    # does is return a plain-text representation of an object.

    if not type in ('preset',):
        raise Http404

    if type == 'preset' and request.GET.get('id', False):
        try:
            preset = PreSetReply.objects.get(id=request.GET.get('id'))
            return HttpResponse(preset.body)
        except PreSetReply.DoesNotExist:
            raise Http404

    raise Http404
raw_details = staff_member_required(raw_details)


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
hold_ticket = staff_member_required(hold_ticket)


def unhold_ticket(request, ticket_id):
    return hold_ticket(request, ticket_id, unhold=True)
unhold_ticket = staff_member_required(unhold_ticket)


def rss_list(request):
    return render_to_response('helpdesk/rss_list.html',
        RequestContext(request, {
            'queues': Queue.objects.all(),
        }))
rss_list = staff_member_required(rss_list)


def report_index(request):
    number_tickets = Ticket.objects.all().count()
    saved_query = request.GET.get('saved_query', None)
    return render_to_response('helpdesk/report_index.html',
        RequestContext(request, {
            'number_tickets': number_tickets,
            'saved_query': saved_query,
        }))
report_index = staff_member_required(report_index)


def run_report(request, report):
    if Ticket.objects.all().count() == 0 or report not in ('queuemonth', 'usermonth', 'queuestatus', 'queuepriority', 'userstatus', 'userpriority', 'userqueue'):
        return HttpResponseRedirect(reverse("helpdesk_report_index"))

    report_queryset = Ticket.objects.all().select_related()
   
    from_saved_query = False
    saved_query = None

    if request.GET.get('saved_query', None):
        from_saved_query = True
        try:
            saved_query = SavedSearch.objects.get(pk=request.GET.get('saved_query'))
        except SavedSearch.DoesNotExist:
            return HttpResponseRedirect(reverse('helpdesk_report_index'))
        if not (saved_query.shared or saved_query.user == request.user):
            return HttpResponseRedirect(reverse('helpdesk_report_index'))

        import cPickle
        from helpdesk.lib import b64decode
        query_params = cPickle.loads(b64decode(str(saved_query.query)))
        report_queryset = apply_query(report_queryset, query_params)

    from collections import defaultdict
    summarytable = defaultdict(int)

    months = (
        _('Jan'),
        _('Feb'),
        _('Mar'),
        _('Apr'),
        _('May'),
        _('Jun'),
        _('Jul'),
        _('Aug'),
        _('Sep'),
        _('Oct'),
        _('Nov'),
        _('Dec'),
    )
    
    first_ticket = Ticket.objects.all().order_by('created')[0]
    first_month = first_ticket.created.month
    first_year = first_ticket.created.year

    last_ticket = Ticket.objects.all().order_by('-created')[0]
    last_month = last_ticket.created.month
    last_year = last_ticket.created.year

    periods = []
    year, month = first_year, first_month
    working = True
    periods.append("%s %s" % (months[month - 1], year))

    while working:
        month += 1
        if month > 12:
            year += 1
            month = 1
        if (year > last_year) or (month > last_month and year >= last_year):
            working = False
        periods.append("%s %s" % (months[month - 1], year))

    if report == 'userpriority':
        title = _('User by Priority')
        col1heading = _('User')
        possible_options = [t[1].__unicode__() for t in Ticket.PRIORITY_CHOICES]
        charttype = 'bar'

    elif report == 'userqueue':
        title = _('User by Queue')
        col1heading = _('User')
        possible_options = [q.title.encode('utf-8') for q in Queue.objects.all()]
        charttype = 'bar'

    elif report == 'userstatus':
        title = _('User by Status')
        col1heading = _('User')
        possible_options = [s[1].__unicode__() for s in Ticket.STATUS_CHOICES]
        charttype = 'bar'

    elif report == 'usermonth':
        title = _('User by Month')
        col1heading = _('User')
        possible_options = periods
        charttype = 'date'

    elif report == 'queuepriority':
        title = _('Queue by Priority')
        col1heading = _('Queue')
        possible_options = [t[1].__unicode__() for t in Ticket.PRIORITY_CHOICES]
        charttype = 'bar'

    elif report == 'queuestatus':
        title = _('Queue by Status')
        col1heading = _('Queue')
        possible_options = [s[1].__unicode__() for s in Ticket.STATUS_CHOICES]
        charttype = 'bar'

    elif report == 'queuemonth':
        title = _('Queue by Month')
        col1heading = _('Queue')
        possible_options = periods
        charttype = 'date'



    for ticket in report_queryset:
        if report == 'userpriority':
            metric1 = u'%s' % ticket.get_assigned_to
            metric2 = u'%s' % ticket.get_priority_display()

        elif report == 'userqueue':
            metric1 = u'%s' % ticket.get_assigned_to
            metric2 = u'%s' % ticket.queue.title

        elif report == 'userstatus':
            metric1 = u'%s' % ticket.get_assigned_to
            metric2 = u'%s' % ticket.get_status_display()

        elif report == 'usermonth':
            metric1 = u'%s' % ticket.get_assigned_to
            metric2 = u'%s %s' % (months[ticket.created.month - 1], ticket.created.year)

        elif report == 'queuepriority':
            metric1 = u'%s' % ticket.queue.title
            metric2 = u'%s' % ticket.get_priority_display()

        elif report == 'queuestatus':
            metric1 = u'%s' % ticket.queue.title
            metric2 = u'%s' % ticket.get_status_display()

        elif report == 'queuemonth':
            metric1 = u'%s' % ticket.queue.title
            metric2 = u'%s %s' % (months[ticket.created.month - 1], ticket.created.year)

        summarytable[metric1, metric2] += 1
    
    table = []
    
    header1 = sorted(set(list( i.encode('utf-8') for i,_ in summarytable.keys() )))
    
    column_headings = [col1heading] + possible_options

    # Pivot the data so that 'header1' fields are always first column
    # in the row, and 'possible_options' are always the 2nd - nth columns.
    for item in header1:
        data = []
        for hdr in possible_options:
            data.append(summarytable[item, hdr])
        table.append([item] + data)

    return render_to_response('helpdesk/report_output.html',
        RequestContext(request, {
            'title': title,
            'charttype': charttype,
            'data': table,
            'headings': column_headings,
            'from_saved_query': from_saved_query,
            'saved_query': saved_query,
        }))
run_report = staff_member_required(run_report)


def save_query(request):
    title = request.POST.get('title', None)
    shared = request.POST.get('shared', False)
    query_encoded = request.POST.get('query_encoded', None)

    if not title or not query_encoded:
        return HttpResponseRedirect(reverse('helpdesk_list'))

    query = SavedSearch(title=title, shared=shared, query=query_encoded, user=request.user)
    query.save()

    return HttpResponseRedirect('%s?saved_query=%s' % (reverse('helpdesk_list'), query.id))
save_query = staff_member_required(save_query)


def delete_saved_query(request, id):
    query = get_object_or_404(SavedSearch, id=id, user=request.user)

    if request.method == 'POST':
        query.delete()
        return HttpResponseRedirect(reverse('helpdesk_list'))
    else:
        return render_to_response('helpdesk/confirm_delete_saved_query.html',
            RequestContext(request, {
                'query': query,
                }))
delete_saved_query = staff_member_required(delete_saved_query)


def user_settings(request):
    s = request.user.usersettings
    if request.POST:
        form = UserSettingsForm(request.POST)
        if form.is_valid():
            s.settings = form.cleaned_data
            s.save()
    else:
        form = UserSettingsForm(s.settings)

    user = User.objects.get(id = request.user.id)
    show_password_change_link = 0
    # we don't want non-local users to see the 'change password' link.
    if helpdesk_settings.HELPDESK_SHOW_CHANGE_PASSWORD and user.has_usable_password():
        show_password_change_link = 1

    return render_to_response('helpdesk/user_settings.html',
        RequestContext(request, {
            'form': form,
            'show_password_change_link': show_password_change_link,
        }))
user_settings = staff_member_required(user_settings)


def email_ignore(request):
    return render_to_response('helpdesk/email_ignore_list.html',
        RequestContext(request, {
            'ignore_list': IgnoreEmail.objects.all(),
        }))
email_ignore = superuser_required(email_ignore)


def email_ignore_add(request):
    if request.method == 'POST':
        form = EmailIgnoreForm(request.POST)
        if form.is_valid():
            ignore = form.save()
            return HttpResponseRedirect(reverse('helpdesk_email_ignore'))
    else:
        form = EmailIgnoreForm(request.GET)

    return render_to_response('helpdesk/email_ignore_add.html',
        RequestContext(request, {
            'form': form,
        }))
email_ignore_add = superuser_required(email_ignore_add)


def email_ignore_del(request, id):
    ignore = get_object_or_404(IgnoreEmail, id=id)
    if request.method == 'POST':
        ignore.delete()
        return HttpResponseRedirect(reverse('helpdesk_email_ignore'))
    else:
        return render_to_response('helpdesk/email_ignore_del.html',
            RequestContext(request, {
                'ignore': ignore,
            }))
email_ignore_del = superuser_required(email_ignore_del)

def ticket_cc(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    copies_to = ticket.ticketcc_set.all()
    return render_to_response('helpdesk/ticket_cc_list.html',
        RequestContext(request, {
            'copies_to': copies_to,
            'ticket': ticket,
        }))
ticket_cc = staff_member_required(ticket_cc)

def ticket_cc_add(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.method == 'POST':
        form = TicketCCForm(request.POST)
        if form.is_valid():
            ticketcc = form.save(commit=False)
            ticketcc.ticket = ticket
            ticketcc.save()
            return HttpResponseRedirect(reverse('helpdesk_ticket_cc', kwargs={'ticket_id': ticket.id}))
    else:
        form = TicketCCForm()
    return render_to_response('helpdesk/ticket_cc_add.html',
        RequestContext(request, {
            'ticket': ticket,
            'form': form,
        }))
ticket_cc_add = staff_member_required(ticket_cc_add)

def ticket_cc_del(request, ticket_id, cc_id):
    cc = get_object_or_404(TicketCC, ticket__id=ticket_id, id=cc_id)
    if request.method == 'POST':
        cc.delete()
        return HttpResponseRedirect(reverse('helpdesk_ticket_cc', kwargs={'ticket_id': cc.ticket.id}))
    return render_to_response('helpdesk/ticket_cc_del.html',
        RequestContext(request, {
            'cc': cc,
        }))
ticket_cc_del = staff_member_required(ticket_cc_del)

def ticket_dependency_add(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.method == 'POST':
        form = TicketDependencyForm(request.POST)
        if form.is_valid():
            ticketdependency = form.save(commit=False)
            ticketdependency.ticket = ticket
            if ticketdependency.ticket <> ticketdependency.depends_on:
                ticketdependency.save()
            return HttpResponseRedirect(reverse('helpdesk_view', args=[ticket.id]))
    else:
        form = TicketDependencyForm()
    return render_to_response('helpdesk/ticket_dependency_add.html',
        RequestContext(request, {
            'ticket': ticket,
            'form': form,
        }))
ticket_dependency_add = staff_member_required(ticket_dependency_add)

def ticket_dependency_del(request, ticket_id, dependency_id):
    dependency = get_object_or_404(TicketDependency, ticket__id=ticket_id, id=dependency_id)
    if request.method == 'POST':
        dependency.delete()
        return HttpResponseRedirect(reverse('helpdesk_view', args=[ticket_id]))
    return render_to_response('helpdesk/ticket_dependency_del.html',
        RequestContext(request, {
            'dependency': dependency,
        }))
ticket_dependency_del = staff_member_required(ticket_dependency_del)

def attachment_del(request, ticket_id, attachment_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    attachment = get_object_or_404(Attachment, id=attachment_id)
    attachment.delete()
    return HttpResponseRedirect(reverse('helpdesk_view', args=[ticket_id]))
attachment_del = staff_member_required(attachment_del)

