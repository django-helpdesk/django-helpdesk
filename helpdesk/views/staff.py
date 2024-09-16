"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/staff.py - The bulk of the application - provides most business logic and
                 renders all staff-facing views.
"""

from ..lib import format_time_spent
from ..templated_email import send_templated_mail
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, time, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.views import redirect_to_login
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.handlers.wsgi import WSGIRequest
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q, Case, When
from django.forms import HiddenInput, inlineformset_factory, TextInput
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.html import escape
from django.utils.timezone import make_aware
from django.utils.translation import gettext as _
from django.views.decorators.csrf import requires_csrf_token
from django.views.generic.edit import FormView, UpdateView
from helpdesk import settings as helpdesk_settings
from helpdesk.decorators import (
    helpdesk_staff_member_required,
    helpdesk_superuser_required,
    is_helpdesk_staff,
    superuser_required
)
from helpdesk.forms import (
    ChecklistForm,
    ChecklistTemplateForm,
    CreateChecklistForm,
    CUSTOMFIELD_DATE_FORMAT,
    EditFollowUpForm,
    EditTicketForm,
    EditTicketCustomFieldForm,
    EmailIgnoreForm,
    FormControlDeleteFormSet,
    MultipleTicketSelectForm,
    TicketCCEmailForm,
    TicketCCForm,
    TicketCCUserForm,
    TicketDependencyForm,
    TicketForm,
    TicketResolvesForm,
    UserSettingsForm
)
from helpdesk.lib import queue_template_context, safe_template_context
from helpdesk.models import (
    Checklist,
    ChecklistTask,
    ChecklistTemplate,
    CustomField,
    FollowUp,
    FollowUpAttachment,
    IgnoreEmail,
    PreSetReply,
    Queue,
    SavedSearch,
    Ticket,
    TicketCC,
    TicketCustomFieldValue,
    TicketDependency,
    UserSettings
)
from helpdesk.query import get_query_class, query_from_base64, query_to_base64
from helpdesk.user import HelpdeskUser
from helpdesk.update_ticket import update_ticket, subscribe_to_ticket_updates, return_ticketccstring_and_show_subscribe
import helpdesk.views.abstract_views as abstract_views
from helpdesk.views.permissions import MustBeStaffMixin
import json
import re
from rest_framework import status
from rest_framework.decorators import api_view
import typing


if helpdesk_settings.HELPDESK_KB_ENABLED:
    from helpdesk.models import KBItem

DATE_RE: re.Pattern = re.compile(
    r'(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{4})$'
)

User = get_user_model()
Query = get_query_class()

if helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE:
    # treat 'normal' users like 'staff'
    staff_member_required = user_passes_test(
        lambda u: u.is_authenticated and u.is_active)
else:
    staff_member_required = user_passes_test(
        lambda u: u.is_authenticated and u.is_active and u.is_staff)


def _get_queue_choices(queues):
    """Return list of `choices` array for html form for given queues

    idea is to return only one choice if there is only one queue or add empty
    choice at the beginning of the list, if there are more queues
    """

    queue_choices = []
    if len(queues) > 1:
        queue_choices = [('', '--------')]
    queue_choices += [(q.id, q.title) for q in queues]
    return queue_choices


@helpdesk_staff_member_required
def dashboard(request):
    """
    A quick summary overview for users: A list of their own tickets, a table
    showing ticket counts by queue/status, and a list of unassigned tickets
    with options for them to 'Take' ownership of said tickets.
    """
    # user settings num tickets per page
    if request.user.is_authenticated and hasattr(request.user, 'usersettings_helpdesk'):
        tickets_per_page = request.user.usersettings_helpdesk.tickets_per_page
    else:
        tickets_per_page = 25

    # page vars for the three ticket tables
    user_tickets_page = request.GET.get(_('ut_page'), 1)
    user_tickets_closed_resolved_page = request.GET.get(_('utcr_page'), 1)
    all_tickets_reported_by_current_user_page = request.GET.get(
        _('atrbcu_page'), 1)

    huser = HelpdeskUser(request.user)
    active_tickets = Ticket.objects.select_related('queue').exclude(
        status__in=[Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS, Ticket.DUPLICATE_STATUS],
    )

    # open & reopened tickets, assigned to current user
    tickets = active_tickets.filter(
        assigned_to=request.user,
    )

    # closed & resolved tickets, assigned to current user
    tickets_closed_resolved = Ticket.objects.select_related('queue').filter(
        assigned_to=request.user,
        status__in=[Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS, Ticket.DUPLICATE_STATUS]
    )

    user_queues = huser.get_queues()

    unassigned_tickets = active_tickets.filter(
        assigned_to__isnull=True,
        queue__in=user_queues
    )
    kbitems = None
    # Teams mode uses assignment via knowledge base items so exclude tickets assigned to KB items
    if helpdesk_settings.HELPDESK_TEAMS_MODE_ENABLED:
        unassigned_tickets = unassigned_tickets.filter(kbitem__isnull=True)
        kbitems = huser.get_assigned_kb_items()

    # all tickets, reported by current user
    all_tickets_reported_by_current_user = ''
    email_current_user = request.user.email
    if email_current_user:
        all_tickets_reported_by_current_user = Ticket.objects.select_related('queue').filter(
            submitter_email=email_current_user,
        ).order_by('status')

    tickets_in_queues = Ticket.objects.filter(
        queue__in=user_queues,
    )
    basic_ticket_stats = calc_basic_ticket_stats(tickets_in_queues)

    # The following query builds a grid of queues & ticket statuses,
    # to be displayed to the user. EG:
    #          Open  Resolved
    # Queue 1    10     4
    # Queue 2     4    12
    # code never used (and prone to sql injections)
    # queues = HelpdeskUser(request.user).get_queues().values_list('id', flat=True)
    # from_clause = """FROM    helpdesk_ticket t,
    #                 helpdesk_queue q"""
    # if queues:
    #     where_clause = """WHERE   q.id = t.queue_id AND
    #                     q.id IN (%s)""" % (",".join(("%d" % pk for pk in queues)))
    # else:
    #     where_clause = """WHERE   q.id = t.queue_id"""

    # get user assigned tickets page
    paginator = Paginator(
        tickets, tickets_per_page)
    try:
        tickets = paginator.page(user_tickets_page)
    except PageNotAnInteger:
        tickets = paginator.page(1)
    except EmptyPage:
        tickets = paginator.page(
            paginator.num_pages)

    # get user completed tickets page
    paginator = Paginator(
        tickets_closed_resolved, tickets_per_page)
    try:
        tickets_closed_resolved = paginator.page(
            user_tickets_closed_resolved_page)
    except PageNotAnInteger:
        tickets_closed_resolved = paginator.page(1)
    except EmptyPage:
        tickets_closed_resolved = paginator.page(
            paginator.num_pages)

    # get user submitted tickets page
    paginator = Paginator(
        all_tickets_reported_by_current_user, tickets_per_page)
    try:
        all_tickets_reported_by_current_user = paginator.page(
            all_tickets_reported_by_current_user_page)
    except PageNotAnInteger:
        all_tickets_reported_by_current_user = paginator.page(1)
    except EmptyPage:
        all_tickets_reported_by_current_user = paginator.page(
            paginator.num_pages)

    return render(request, 'helpdesk/dashboard.html', {
        'user_tickets': tickets,
        'user_tickets_closed_resolved': tickets_closed_resolved,
        'unassigned_tickets': unassigned_tickets,
        'kbitems': kbitems,
        'all_tickets_reported_by_current_user': all_tickets_reported_by_current_user,
        'basic_ticket_stats': basic_ticket_stats,
    })


dashboard = staff_member_required(dashboard)


def ticket_perm_check(request, ticket):
    huser = HelpdeskUser(request.user)
    if not huser.can_access_queue(ticket.queue):
        raise PermissionDenied()
    if not huser.can_access_ticket(ticket):
        raise PermissionDenied()


@helpdesk_staff_member_required
def delete_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    if request.method == 'GET':
        return render(request, 'helpdesk/delete_ticket.html', {
            'ticket': ticket,
            'next': request.GET.get('next', 'home')
        })
    else:
        ticket.delete()
        redirect_to = 'helpdesk:home'
        if request.POST.get('next') == 'dashboard':
            redirect_to = 'helpdesk:dashboard'
        return HttpResponseRedirect(reverse(redirect_to))


delete_ticket = staff_member_required(delete_ticket)


@helpdesk_staff_member_required
def followup_edit(request, ticket_id, followup_id):
    """Edit followup options with an ability to change the ticket."""
    followup = get_object_or_404(FollowUp, id=followup_id)
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    if request.method == 'GET':
        form = EditFollowUpForm(initial={
            'title': escape(followup.title),
            'ticket': followup.ticket,
            'comment': escape(followup.comment),
            'public': followup.public,
            'new_status': followup.new_status,
            'time_spent': format_time_spent(followup.time_spent),
        })

        ticketcc_string = return_ticketccstring_and_show_subscribe(request.user, ticket)[0]

        return render(request, 'helpdesk/followup_edit.html', {
            'followup': followup,
            'ticket': ticket,
            'form': form,
            'ticketcc_string': ticketcc_string,
        })
    elif request.method == 'POST':
        form = EditFollowUpForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            _ticket = form.cleaned_data['ticket']
            comment = form.cleaned_data['comment']
            public = form.cleaned_data['public']
            new_status = form.cleaned_data['new_status']
            time_spent = form.cleaned_data['time_spent']
            # will save previous date
            old_date = followup.date
            new_followup = FollowUp(title=title, date=old_date, ticket=_ticket,
                                    comment=comment, public=public,
                                    new_status=new_status,
                                    time_spent=time_spent)
            # keep old user if one did exist before.
            if followup.user:
                new_followup.user = followup.user
            new_followup.save()
            # get list of old attachments & link them to new_followup
            attachments = FollowUpAttachment.objects.filter(followup=followup)
            for attachment in attachments:
                attachment.followup = new_followup
                attachment.save()
            # delete old followup
            followup.delete()
        return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket.id]))


followup_edit = staff_member_required(followup_edit)


@helpdesk_staff_member_required
def followup_delete(request, ticket_id, followup_id):
    """followup delete for superuser"""

    ticket = get_object_or_404(Ticket, id=ticket_id)
    if not request.user.is_superuser:
        return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket.id]))

    followup = get_object_or_404(FollowUp, id=followup_id)
    followup.delete()
    return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket.id]))


followup_delete = staff_member_required(followup_delete)


@helpdesk_staff_member_required
def view_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    if 'take' in request.GET:
        update_ticket(
            request.user,
            ticket,
            owner=request.user.id
        )
        return return_to_ticket(request.user, helpdesk_settings, ticket)

    if 'subscribe' in request.GET:
        # Allow the user to subscribe him/herself to the ticket whilst viewing
        # it.
        show_subscribe = return_ticketccstring_and_show_subscribe(
            request.user, ticket
        )[1]

        if show_subscribe:
            subscribe_to_ticket_updates(ticket, request.user)
            return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket.id]))

    if 'close' in request.GET and ticket.status == Ticket.RESOLVED_STATUS:
        if not ticket.assigned_to:
            owner = 0
        else:
            owner = ticket.assigned_to.id

        update_ticket(
            request.user,
            ticket,
            owner=owner,
            comment= _('Accepted resolution and closed ticket'),
        )
        return return_to_ticket(request.user, helpdesk_settings, ticket)

    if helpdesk_settings.HELPDESK_STAFF_ONLY_TICKET_OWNERS:
        users = User.objects.filter(
            is_active=True, is_staff=True).order_by(User.USERNAME_FIELD)
    else:
        users = User.objects.filter(
            is_active=True).order_by(User.USERNAME_FIELD)

    queues = HelpdeskUser(request.user).get_queues()
    queue_choices = _get_queue_choices(queues)
    # TODO: shouldn't this template get a form to begin with?
    form = TicketForm(initial={'due_date': ticket.due_date},
                      queue_choices=queue_choices)

    ticketcc_string, show_subscribe = \
        return_ticketccstring_and_show_subscribe(request.user, ticket)

    submitter_userprofile = ticket.get_submitter_userprofile()
    if submitter_userprofile is not None:
        content_type = ContentType.objects.get_for_model(submitter_userprofile)
        submitter_userprofile_url = reverse(
            'admin:{app}_{model}_change'.format(
                app=content_type.app_label, model=content_type.model),
            kwargs={'object_id': submitter_userprofile.id}
        )
    else:
        submitter_userprofile_url = None

    checklist_form = CreateChecklistForm(request.POST or None)
    if checklist_form.is_valid():
        checklist = checklist_form.save(commit=False)
        checklist.ticket = ticket
        checklist.save()

        checklist_template = checklist_form.cleaned_data.get('checklist_template')
        # Add predefined tasks if template has been selected
        if checklist_template:
            checklist.create_tasks_from_template(checklist_template)

        return redirect('helpdesk:edit_ticket_checklist', ticket.id, checklist.id)

    # List open tickets on top
    dependencies = ticket.ticketdependency.annotate(
        rank=Case(
                When(depends_on__status__in=Ticket.OPEN_STATUSES, then=1),
                default=2
        )).order_by('rank')
    
    # add custom fields to further details panel
    customfields_form = EditTicketCustomFieldForm(None, instance=ticket)

    return render(request, 'helpdesk/ticket.html', {
        'ticket': ticket,
        'dependencies': dependencies,
        'submitter_userprofile_url': submitter_userprofile_url,
        'form': form,
        'active_users': users,
        'priorities': Ticket.PRIORITY_CHOICES,
        'queues': queue_choices,
        'preset_replies': PreSetReply.objects.filter(
            Q(queues=ticket.queue) | Q(queues__isnull=True)),
        'ticketcc_string': ticketcc_string,
        'SHOW_SUBSCRIBE': show_subscribe,
        'checklist_form': checklist_form,
        'customfields_form': customfields_form,
    })


@helpdesk_staff_member_required
def edit_ticket_checklist(request, ticket_id, checklist_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)
    checklist = get_object_or_404(ticket.checklists.all(), id=checklist_id)

    form = ChecklistForm(request.POST or None, instance=checklist)
    TaskFormSet = inlineformset_factory(
        Checklist,
        ChecklistTask,
        formset=FormControlDeleteFormSet,
        fields=['description', 'position'],
        widgets={
            'position': HiddenInput(),
            'description': TextInput(attrs={'class': 'form-control'}),
        },
        can_delete=True,
        extra=0
    )
    formset = TaskFormSet(request.POST or None, instance=checklist)
    if form.is_valid() and formset.is_valid():
        form.save()
        formset.save()
        return redirect(ticket)

    return render(request, 'helpdesk/checklist_form.html', {
        'ticket': ticket,
        'checklist': checklist,
        'form': form,
        'formset': formset,
    })


@helpdesk_staff_member_required
def delete_ticket_checklist(request, ticket_id, checklist_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)
    checklist = get_object_or_404(ticket.checklists.all(), id=checklist_id)

    if request.method == 'POST':
        checklist.delete()
        return redirect(ticket)

    return render(request, 'helpdesk/checklist_confirm_delete.html', {
        'ticket': ticket,
        'checklist': checklist,
    })


def get_ticket_from_request_with_authorisation(
    request: WSGIRequest,
    ticket_id: str,
    public: bool
) -> Ticket:
    """Gets a ticket from the public status and if the user is authenticated and
    has permissions to update tickets

    Raises:
        Http404 when the ticket can not be found or the user lacks permission

    """
    if not (public or (
            request.user.is_authenticated and
            request.user.is_active and (
                is_helpdesk_staff(request.user) or
                helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE))):

        try:
            return Ticket.objects.get(
                id=ticket_id,
                submitter_email__iexact=request.POST.get('mail'),
                secret_key__iexact=request.POST.get('key')
            )
        except (Ticket.DoesNotExist, ValueError):
            raise PermissionDenied()

    return get_object_or_404(Ticket, id=ticket_id)


def get_due_date_from_request_or_ticket(
    request: WSGIRequest,
    ticket: Ticket
) -> typing.Optional[datetime.date]:
    """Tries to locate the due date for a ticket from the `request.POST`
    'due_date' parameter or the `due_date_*` paramaters.
    """
    due_date = request.POST.get('due_date', None) or None

    if due_date is not None:
        parsed_date = parse_datetime(due_date) or datetime.combine(parse_date(due_date), time())
        due_date = make_aware(parsed_date)
    else:
        due_date_year = int(request.POST.get('due_date_year', 0))
        due_date_month = int(request.POST.get('due_date_month', 0))
        due_date_day = int(request.POST.get('due_date_day', 0))
        # old way, probably deprecated?
        if not (due_date_year and due_date_month and due_date_day):
            due_date = ticket.due_date
        else:
            # NOTE: must be an easier way to create a new date than doing it
            # this way?
            if ticket.due_date:
                due_date = ticket.due_date
            else:
                due_date = timezone.now()
                due_date = due_date.replace(
                    due_date_year, due_date_month, due_date_day)
    return due_date


def get_time_spent_from_request(request: WSGIRequest) -> typing.Optional[timedelta]:
    if request.POST.get("time_spent"):
        (hours, minutes) = [int(f)
                            for f in request.POST.get("time_spent").split(":")]
        return timedelta(hours=hours, minutes=minutes)
    return None


def update_ticket_view(request, ticket_id, public=False):

    try:
        ticket = get_ticket_from_request_with_authorisation(request, ticket_id, public)
    except PermissionDenied:
        return redirect_to_login(request.path, 'helpdesk:login')

    comment = request.POST.get('comment', '')
    new_status = int(request.POST.get('new_status', ticket.status))
    title = request.POST.get('title', ticket.title)
    owner = int(request.POST.get('owner', -1))
    priority = int(request.POST.get('priority', ticket.priority))
    queue = int(request.POST.get('queue', ticket.queue.id))

    # custom fields
    customfields_form = EditTicketCustomFieldForm(request.POST or None,
                                                  instance=ticket)

    # Check if a change happened on checklists
    new_checklists = {}
    changes_in_checklists = False
    for checklist in ticket.checklists.all():
        old_completed = set(checklist.tasks.completed().values_list('id', flat=True))
        new_checklist = set(map(int, request.POST.getlist(f'checklist-{checklist.id}', [])))
        new_checklists[checklist.id] = new_checklist
        if new_checklist != old_completed:
            changes_in_checklists = True

    time_spent = get_time_spent_from_request(request)
    # NOTE: jQuery's default for dates is mm/dd/yy
    # very US-centric but for now that's the only format supported
    # until we clean up code to internationalize a little more
    due_date = get_due_date_from_request_or_ticket(request, ticket)
    no_changes = all([
        not request.FILES,
        not comment,
        not changes_in_checklists,
        new_status == ticket.status,
        title == ticket.title,
        priority == int(ticket.priority),
        queue == int(ticket.queue.id),
        due_date == ticket.due_date,
        (owner == -1) or (not owner and not ticket.assigned_to) or
        (owner and User.objects.get(id=owner) == ticket.assigned_to),
        not customfields_form.has_changed(),
    ])
    if no_changes:
        return return_to_ticket(request.user, helpdesk_settings, ticket)

    update_ticket(
        request.user,
        ticket,
        title = title,
        comment = comment,
        files = request.FILES.getlist('attachment'),
        public = request.POST.get('public', False),
        owner = int(request.POST.get('owner', -1)),
        priority = int(request.POST.get('priority', -1)),
        queue = int(request.POST.get('queue', -1)),
        new_status = new_status,
        time_spent = get_time_spent_from_request(request),
        due_date = get_due_date_from_request_or_ticket(request, ticket),
        new_checklists = new_checklists,
        customfields_form = customfields_form,
    )

    return return_to_ticket(request.user, helpdesk_settings, ticket)


def return_to_ticket(user, helpdesk_settings, ticket):
    """Helper function for update_ticket"""

    if is_helpdesk_staff(user):
        return HttpResponseRedirect(ticket.get_absolute_url())
    else:
        return HttpResponseRedirect(ticket.ticket_url)


@helpdesk_staff_member_required
def mass_update(request):
    tickets = request.POST.getlist('ticket_id')
    action = request.POST.get('action', None)
    if not (tickets and action):
        return HttpResponseRedirect(reverse('helpdesk:list'))

    user = kbitem = None

    if action.startswith('assign_'):
        parts = action.split('_')
        user = User.objects.get(id=parts[1])
        action = 'assign'
    if action == 'kbitem_none':
        action = 'set_kbitem'
    if action.startswith('kbitem_'):
        parts = action.split('_')
        kbitem = KBItem.objects.get(id=parts[1])
        action = 'set_kbitem'
    elif action == 'take':
        user = request.user
        action = 'assign'
    elif action == 'merge':
        # Redirect to the Merge View with selected tickets id in the GET
        # request
        return redirect(
            reverse('helpdesk:merge_tickets') + '?' +
            '&'.join(['tickets=%s' % ticket_id for ticket_id in tickets])
        )

    huser = HelpdeskUser(request.user)
    for t in Ticket.objects.filter(id__in=tickets):
        if not huser.can_access_queue(t.queue):
            continue

        if action == 'assign' and t.assigned_to != user:
            t.assigned_to = user
            t.save()
            t.followup_set.create(
                date=timezone.now(),
                title=_('Assigned to %(username)s in bulk update' % {'username': user.get_username()}),
                public=True,
                user=request.user
            )
        elif action == 'unassign' and t.assigned_to is not None:
            t.assigned_to = None
            t.save()
            t.followup_set.create(
                date=timezone.now(),
                title=_('Unassigned in bulk update'),
                public=True,
                user=request.user
            )
        elif action == 'set_kbitem':
            t.kbitem = kbitem
            t.save()
            t.followup_set.create(
                date=timezone.now(),
                title=_('KBItem set in bulk update'),
                public=False,
                user=request.user
            )
        elif action == 'close' and t.status != Ticket.CLOSED_STATUS:
            t.status = Ticket.CLOSED_STATUS
            t.save()
            t.followup_set.create(
                date=timezone.now(),
                title=_('Closed in bulk update'),
                public=False,
                user=request.user,
                new_status=Ticket.CLOSED_STATUS
            )
        elif action == 'close_public' and t.status != Ticket.CLOSED_STATUS:
            t.status = Ticket.CLOSED_STATUS
            t.save()
            t.followup_set.create(
                date=timezone.now(),
                title=_('Closed in bulk update'),
                public=True,
                user=request.user,
                new_status=Ticket.CLOSED_STATUS
            )
            # Send email to Submitter, Owner, Queue CC
            context = safe_template_context(t)
            context.update(resolution=t.resolution,
                           queue=queue_template_context(t.queue))

            messages_sent_to = set()
            try:
                messages_sent_to.add(request.user.email)
            except AttributeError:
                pass

            roles = {
                'submitter': ('closed_submitter', context),
                'ticket_cc': ('closed_cc', context),
            }
            if t.assigned_to and t.assigned_to.usersettings_helpdesk.email_on_ticket_change:
                roles['assigned_to'] = ('closed_owner', context)

            messages_sent_to.update(t.send(
                roles,
                dont_send_to=messages_sent_to,
                fail_silently=True,
            ))

        elif action == 'delete':
            t.delete()

    return HttpResponseRedirect(reverse('helpdesk:list'))


mass_update = staff_member_required(mass_update)


# Prepare ticket attributes which will be displayed in the table to choose
# which value to keep when merging
TICKET_ATTRIBUTES = (
    ('created', _('Created date')),
    ('due_date', _('Due on')),
    ('get_status_display', _('Status')),
    ('submitter_email', _('Submitter email')),
    ('assigned_to', _('Owner')),
    ('description', _('Description')),
    ('resolution', _('Resolution')),
)


def merge_ticket_values(
        request: WSGIRequest,
        tickets: typing.List[Ticket],
        custom_fields
) -> None:
    for ticket in tickets:
        ticket.values = {}
        # Prepare the value for each attributes of this ticket
        for attribute, __ in TICKET_ATTRIBUTES:
            value = getattr(ticket, attribute, TicketCustomFieldValue.default_value)
            # Check if attr is a get_FIELD_display
            if attribute.startswith('get_') and attribute.endswith('_display'):
                # Hack to call methods like get_FIELD_display()
                value = getattr(ticket, attribute, TicketCustomFieldValue.default_value)()
            ticket.values[attribute] = {
                'value': value,
                'checked': str(ticket.id) == request.POST.get(attribute)
            }
        # Prepare the value for each custom fields of this ticket
        for custom_field in custom_fields:
            try:
                value = ticket.ticketcustomfieldvalue_set.get(
                    field=custom_field).value
            except (TicketCustomFieldValue.DoesNotExist, ValueError):
                value = TicketCustomFieldValue.default_value
            ticket.values[custom_field.name] = {
                'value': value,
                'checked': str(ticket.id) == request.POST.get(custom_field.name)
            }


def redirect_from_chosen_ticket(
    request,
    chosen_ticket,
    tickets,
    custom_fields
) -> HttpResponseRedirect:
    # Save ticket fields values
    for attribute, __ in TICKET_ATTRIBUTES:
        id_for_attribute = request.POST.get(attribute)
        if id_for_attribute != chosen_ticket.id:
            try:
                selected_ticket = tickets.get(id=id_for_attribute)
            except (Ticket.DoesNotExist, ValueError):
                continue

            # Check if attr is a get_FIELD_display
            if attribute.startswith('get_') and attribute.endswith('_display'):
                # Keep only the FIELD part
                attribute = attribute[4:-8]
            # Get value from selected ticket and then save it on
            # the chosen ticket
            value = getattr(selected_ticket, attribute)
            setattr(chosen_ticket, attribute, value)
    # Save custom fields values
    for custom_field in custom_fields:
        id_for_custom_field = request.POST.get(custom_field.name)
        if id_for_custom_field != chosen_ticket.id:
            try:
                selected_ticket = tickets.get(
                    id=id_for_custom_field)
            except (Ticket.DoesNotExist, ValueError):
                continue

            # Check if the value for this ticket custom field
            # exists
            try:
                value = selected_ticket.ticketcustomfieldvalue_set.get(
                    field=custom_field).value
            except TicketCustomFieldValue.DoesNotExist:
                continue

            # Create the custom field value or update it with the
            # value from the selected ticket
            custom_field_value, created = chosen_ticket.ticketcustomfieldvalue_set.get_or_create(
                field=custom_field,
                defaults={'value': value}
            )
            if not created:
                custom_field_value.value = value
                custom_field_value.save(update_fields=['value'])
    # Save changes
    chosen_ticket.save()

    # For other tickets, save the link to the ticket in which they have been merged to
    # and set status to DUPLICATE
    for ticket in tickets.exclude(id=chosen_ticket.id):
        ticket.merged_to = chosen_ticket
        ticket.status = Ticket.DUPLICATE_STATUS
        ticket.save()

        # Send mail to submitter email and ticket CC to let them
        # know ticket has been merged
        context = safe_template_context(ticket)
        if ticket.submitter_email:
            send_templated_mail(
                template_name='merged',
                context=context,
                recipients=[ticket.submitter_email],
                bcc=[
                    cc.email_address for cc in ticket.ticketcc_set.select_related('user')],
                sender=ticket.queue.from_address,
                fail_silently=True
            )

        # Move all followups and update their title to know they
        # come from another ticket
        ticket.followup_set.update(
            ticket=chosen_ticket,
            # Next might exceed maximum 200 characters limit
            title=_('[Merged from #%(id)d] %(title)s') % {
                'id': ticket.id, 'title': ticket.title}
        )

        # Add submitter_email, assigned_to email and ticketcc to
        # chosen ticket if necessary
        chosen_ticket.add_email_to_ticketcc_if_not_in(
            email=ticket.submitter_email)
        if ticket.assigned_to and ticket.assigned_to.email:
            chosen_ticket.add_email_to_ticketcc_if_not_in(
                email=ticket.assigned_to.email)
        for ticketcc in ticket.ticketcc_set.all():
            chosen_ticket.add_email_to_ticketcc_if_not_in(
                ticketcc=ticketcc)
    return redirect(chosen_ticket)


@staff_member_required
def merge_tickets(request):
    """
    An intermediate view to merge up to 3 tickets in one main ticket.
    The user has to first select which ticket will receive the other tickets information and can also choose which
    data to keep per attributes as well as custom fields.
    Follow-ups and ticketCC will be moved to the main ticket and other tickets won't be able to receive new answers.
    """
    ticket_select_form = MultipleTicketSelectForm(request.GET or None)
    tickets = custom_fields = None
    if ticket_select_form.is_valid():
        tickets = ticket_select_form.cleaned_data.get('tickets')

        custom_fields = CustomField.objects.all()

        merge_ticket_values(request, tickets, custom_fields)

        if request.method == 'POST':
            # Find which ticket has been chosen to be the main one
            try:
                chosen_ticket = tickets.get(
                    id=request.POST.get('chosen_ticket'))
            except Ticket.DoesNotExist:
                ticket_select_form.add_error(
                    field='tickets',
                    error=_(
                        'Please choose a ticket in which the others will be merged into.')
                )
            else:
                return redirect_from_chosen_ticket(
                    request,
                    chosen_ticket,
                    tickets,
                    custom_fields
                )

    return render(request, 'helpdesk/ticket_merge.html', {
        'tickets': tickets,
        'ticket_attributes': TICKET_ATTRIBUTES,
        'custom_fields': custom_fields,
        'ticket_select_form': ticket_select_form
    })


def check_redirect_on_user_query(request, huser):
    """If the user is coming from the header/navigation search box, lets' first
    look at their query to see if they have entered a valid ticket number. If
    they have, just redirect to that ticket number. Otherwise, we treat it as
    a keyword search.
    """
    if request.GET.get('search_type', None) == 'header':
        query = request.GET.get('q')
        filter_ = None
        if query.find('-') > 0:
            try:
                queue, id_ = Ticket.queue_and_id_from_query(query)
                id_ = int(id_)
            except ValueError:
                pass
            else:
                filter_ = {'queue__slug': queue, 'id': id_}
        else:
            try:
                query = int(query)
            except ValueError:
                pass
            else:
                filter_ = {'id': int(query)}

        if filter_:
            try:
                ticket = huser.get_tickets_in_queues().get(**filter_)
                return HttpResponseRedirect(ticket.staff_url)
            except Ticket.DoesNotExist:
                # Go on to standard keyword searching
                pass
    return None


@helpdesk_staff_member_required
def ticket_list(request):
    context = {}

    huser = HelpdeskUser(request.user)

    # Query_params will hold a dictionary of parameters relating to
    # a query, to be saved if needed:
    query_params = {
        'filtering': {},
        'filtering_or': {},
        'sorting': None,
        'sortreverse': False,
        'search_string': '',
    }
    default_query_params = {
        'filtering': {
            'status__in': [1, 2],
        },
        'sorting': 'created',
        'search_string': '',
        'sortreverse': False,
    }

    #: check for a redirect, see function doc for details
    redirect = check_redirect_on_user_query(request, huser)
    if redirect:
        return redirect
    try:
        saved_query, query_params = load_saved_query(request, query_params)
    except QueryLoadError:
        return HttpResponseRedirect(reverse('helpdesk:list'))

    if saved_query:
        pass
    elif not {'queue', 'assigned_to', 'status', 'q', 'sort', 'sortreverse', 'kbitem'}.intersection(request.GET):
        # Fall-back if no querying is being done
        query_params = deepcopy(default_query_params)
    else:
        filter_in_params = [
            ('queue', 'queue__id__in'),
            ('assigned_to', 'assigned_to__id__in'),
            ('status', 'status__in'),
            ('kbitem', 'kbitem__in'),
        ]
        filter_null_params = dict([
            ('queue', 'queue__id__isnull'),
            ('assigned_to', 'assigned_to__id__isnull'),
            ('status', 'status__isnull'),
            ('kbitem', 'kbitem__isnull'),
        ])
        for param, filter_command in filter_in_params:
            if request.GET.get(param) is not None:
                patterns = request.GET.getlist(param)
                try:
                    pattern_pks = [int(pattern) for pattern in patterns]
                    if -1 in pattern_pks:
                        query_params['filtering_or'][filter_null_params[param]] = True
                    else:
                        query_params['filtering_or'][filter_command] = pattern_pks
                    query_params['filtering'][filter_command] = pattern_pks
                except ValueError:
                    pass

        date_from = request.GET.get('date_from')
        if date_from:
            query_params['filtering']['created__gte'] = date_from

        date_to = request.GET.get('date_to')
        if date_to:
            query_params['filtering']['created__lte'] = date_to

        # KEYWORD SEARCHING
        q = request.GET.get('q', '')
        context['query'] = q
        query_params['search_string'] = q

        # SORTING
        sort = request.GET.get('sort', None)
        if sort not in ('status', 'assigned_to', 'created', 'title', 'queue', 'priority', 'kbitem'):
            sort = 'created'
        query_params['sorting'] = sort

        sortreverse = request.GET.get('sortreverse', None)
        query_params['sortreverse'] = sortreverse

    urlsafe_query = query_to_base64(query_params)

    user_saved_queries = SavedSearch.objects.filter(
        Q(user=request.user) | Q(shared__exact=True))

    search_message = ''
    if query_params['search_string'] and settings.DATABASES['default']['ENGINE'].endswith('sqlite'):
        search_message = _(
            '<p><strong>Note:</strong> Your keyword search is case sensitive '
            'because of your database. This means the search will <strong>not</strong> '
            'be accurate. By switching to a different database system you will gain '
            'better searching! For more information, read the '
            '<a href="http://docs.djangoproject.com/en/dev/ref/databases/#sqlite-string-matching">'
            'Django Documentation on string matching in SQLite</a>.')

    kbitem_choices = []
    kbitem = []

    if helpdesk_settings.HELPDESK_KB_ENABLED:
        kbitem_choices = [(item.pk, str(item))
                          for item in KBItem.objects.all()]
        kbitem = KBItem.objects.all()

    return render(request, 'helpdesk/ticket_list.html', dict(
        context,
        default_tickets_per_page=request.user.usersettings_helpdesk.tickets_per_page,
        user_choices=User.objects.filter(is_active=True, is_staff=True),
        kb_items=kbitem,
        queue_choices=huser.get_queues(),
        status_choices=Ticket.STATUS_CHOICES,
        kbitem_choices=kbitem_choices,
        urlsafe_query=urlsafe_query,
        user_saved_queries=user_saved_queries,
        query_params=query_params,
        from_saved_query=saved_query is not None,
        saved_query=saved_query,
        search_message=search_message,
        helpdesk_settings=helpdesk_settings,
    ))


ticket_list = staff_member_required(ticket_list)


class QueryLoadError(Exception):
    pass


def load_saved_query(request, query_params=None):
    saved_query = None

    if request.GET.get('saved_query', None):
        try:
            saved_query = SavedSearch.objects.get(
                Q(pk=request.GET.get('saved_query')) & (
                    Q(shared=True) | Q(user=request.user))
            )
        except (SavedSearch.DoesNotExist, ValueError):
            raise QueryLoadError()

        try:
            # we get a string like: b'stuff'
            # so leave of the first two chars (b') and last (')
            if saved_query.query.startswith('b\''):
                b64query = saved_query.query[2:-1]
            else:
                b64query = saved_query.query
            query_params = query_from_base64(b64query)
        except json.JSONDecodeError:
            raise QueryLoadError()
    return saved_query, query_params


@helpdesk_staff_member_required
@api_view(['GET'])
def datatables_ticket_list(request, query):
    """
    Datatable on ticket_list.html uses this view from to get objects to display
    on the table. query_tickets_by_args is at lib.py, DatatablesTicketSerializer is in
    serializers.py. The serializers and this view use django-rest_framework methods
    """
    query = Query(HelpdeskUser(request.user), base64query=query)
    result = query.get_datatables_context(**request.query_params)
    return JsonResponse(result, status=status.HTTP_200_OK)


@helpdesk_staff_member_required
@api_view(['GET'])
def timeline_ticket_list(request, query):
    query = Query(HelpdeskUser(request.user), base64query=query)
    return JsonResponse(query.get_timeline_context(), status=status.HTTP_200_OK)


@helpdesk_staff_member_required
def edit_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    form = EditTicketForm(request.POST or None, instance=ticket)
    if form.is_valid():
        ticket = form.save()
        return redirect(ticket)

    return render(request, 'helpdesk/edit_ticket.html', {'form': form, 'ticket': ticket, 'errors': form.errors})


edit_ticket = staff_member_required(edit_ticket)


class CreateTicketView(MustBeStaffMixin, abstract_views.AbstractCreateTicketMixin, FormView):
    template_name = 'helpdesk/create_ticket.html'
    form_class = TicketForm

    def get_initial(self):
        initial_data = super().get_initial()
        return initial_data

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        queues = HelpdeskUser(self.request.user).get_queues()
        kwargs["queue_choices"] = _get_queue_choices(queues)
        return kwargs

    def form_valid(self, form):
        self.ticket = form.save(
            user=self.request.user if self.request.user.is_authenticated else None)
        return super().form_valid(form)

    def get_success_url(self):
        request = self.request
        if HelpdeskUser(request.user).can_access_queue(self.ticket.queue):
            return self.ticket.get_absolute_url()
        else:
            return reverse('helpdesk:dashboard')


@helpdesk_staff_member_required
def raw_details(request, type_):
    # TODO: This currently only supports spewing out 'PreSetReply' objects,
    # in the future it needs to be expanded to include other items. All it
    # does is return a plain-text representation of an object.

    if type_ not in ('preset',):
        raise Http404

    if type_ == 'preset' and request.GET.get('id', False):
        try:
            preset = PreSetReply.objects.get(id=request.GET.get('id'))
            return HttpResponse(preset.body)
        except PreSetReply.DoesNotExist:
            raise Http404

    raise Http404


raw_details = staff_member_required(raw_details)


@helpdesk_staff_member_required
@requires_csrf_token
def hold_ticket(request, ticket_id, unhold=False):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    if unhold:
        ticket.on_hold = False
        title = _('Ticket taken off hold')
    else:
        ticket.on_hold = True
        title = _('Ticket placed on hold')

    f = update_ticket(
        user=request.user,
        ticket=ticket,
        title=title,
        public=True,
    )
    f.save()

    ticket.save()

    return HttpResponseRedirect(ticket.get_absolute_url())


hold_ticket = staff_member_required(hold_ticket)


@helpdesk_staff_member_required
@requires_csrf_token
def unhold_ticket(request, ticket_id):
    return hold_ticket(request, ticket_id, unhold=True)


unhold_ticket = staff_member_required(unhold_ticket)


@helpdesk_staff_member_required
def rss_list(request):
    return render(request, 'helpdesk/rss_list.html', {'queues': Queue.objects.all()})


rss_list = staff_member_required(rss_list)


@helpdesk_staff_member_required
def report_index(request):
    number_tickets = Ticket.objects.all().count()
    saved_query = request.GET.get('saved_query', None)

    user_queues = HelpdeskUser(request.user).get_queues()
    Tickets = Ticket.objects.filter(queue__in=user_queues)
    basic_ticket_stats = calc_basic_ticket_stats(Tickets)

    # The following query builds a grid of queues & ticket statuses,
    # to be displayed to the user. EG:
    #          Open  Resolved
    # Queue 1    10     4
    # Queue 2     4    12
    Queues = user_queues if user_queues else Queue.objects.all()

    dash_tickets = []
    for queue in Queues:
        dash_ticket = {
            'queue': queue.id,
            'name': queue.title,
            'open': queue.ticket_set.filter(status__in=[1, 2]).count(),
            'resolved': queue.ticket_set.filter(status=3).count(),
            'closed': queue.ticket_set.filter(status=4).count(),
            'time_spent': format_time_spent(queue.time_spent),
            'dedicated_time': format_time_spent(queue.dedicated_time)
        }
        dash_tickets.append(dash_ticket)

    return render(request, 'helpdesk/report_index.html', {
        'number_tickets': number_tickets,
        'saved_query': saved_query,
        'basic_ticket_stats': basic_ticket_stats,
        'dash_tickets': dash_tickets,
    })


report_index = staff_member_required(report_index)


def get_report_queryset_or_redirect(request, report):
    if Ticket.objects.all().count() == 0 or report not in (
        "queuemonth",
        "usermonth",
        "queuestatus",
        "queuepriority",
        "userstatus",
        "userpriority",
        "userqueue",
        "daysuntilticketclosedbymonth"
    ):
        return None, None, HttpResponseRedirect(reverse("helpdesk:report_index"))

    report_queryset = Ticket.objects.all().select_related().filter(
        queue__in=HelpdeskUser(request.user).get_queues()
    )

    try:
        saved_query, query_params = load_saved_query(request)
    except QueryLoadError:
        return None, HttpResponseRedirect(reverse('helpdesk:report_index'))
    return report_queryset, query_params, saved_query, None


def get_report_table_and_totals(header1, summarytable, possible_options):
    table = []
    totals = {}
    for item in header1:
        data = []
        for hdr in possible_options:
            if hdr not in totals.keys():
                totals[hdr] = summarytable[item, hdr]
            else:
                totals[hdr] += summarytable[item, hdr]
            data.append(summarytable[item, hdr])
        table.append([item] + data)
    return table, totals


def update_summary_tables(report_queryset, report, summarytable, summarytable2):
    metric3 = False
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
            metric2 = u'%s-%s' % (ticket.created.year, ticket.created.month)

        elif report == 'queuepriority':
            metric1 = u'%s' % ticket.queue.title
            metric2 = u'%s' % ticket.get_priority_display()

        elif report == 'queuestatus':
            metric1 = u'%s' % ticket.queue.title
            metric2 = u'%s' % ticket.get_status_display()

        elif report == 'queuemonth':
            metric1 = u'%s' % ticket.queue.title
            metric2 = u'%s-%s' % (ticket.created.year, ticket.created.month)

        elif report == 'daysuntilticketclosedbymonth':
            metric1 = u'%s' % ticket.queue.title
            metric2 = u'%s-%s' % (ticket.created.year, ticket.created.month)
            metric3 = ticket.modified - ticket.created
            metric3 = metric3.days

        else:
            raise ValueError(f'report "{report}" is unrecognized.')

        summarytable[metric1, metric2] += 1
        if metric3:
            if report == 'daysuntilticketclosedbymonth':
                summarytable2[metric1, metric2] += metric3


@helpdesk_staff_member_required
def run_report(request, report):

    report_queryset, query_params, saved_query, redirect = get_report_queryset_or_redirect(
        request, report
    )
    if redirect:
        return redirect
    if request.GET.get('saved_query', None):
        Query(report_queryset, query_to_base64(query_params))

    summarytable = defaultdict(int)
    # a second table for more complex queries
    summarytable2 = defaultdict(int)

    first_ticket = Ticket.objects.all().order_by('created')[0]
    first_month = first_ticket.created.month
    first_year = first_ticket.created.year

    last_ticket = Ticket.objects.all().order_by('-created')[0]
    last_month = last_ticket.created.month
    last_year = last_ticket.created.year

    periods = []
    year, month = first_year, first_month
    working = True
    periods.append("%s-%s" % (year, month))

    while working:
        month += 1
        if month > 12:
            year += 1
            month = 1
        if (year > last_year) or (month > last_month and year >= last_year):
            working = False
        periods.append("%s-%s" % (year, month))

    if report == 'userpriority':
        title = _('User by Priority')
        col1heading = _('User')
        possible_options = [t[1].title() for t in Ticket.PRIORITY_CHOICES]
        charttype = 'bar'

    elif report == 'userqueue':
        title = _('User by Queue')
        col1heading = _('User')
        queue_options = HelpdeskUser(request.user).get_queues()
        possible_options = [q.title for q in queue_options]
        charttype = 'bar'

    elif report == 'userstatus':
        title = _('User by Status')
        col1heading = _('User')
        possible_options = [s[1].title() for s in Ticket.STATUS_CHOICES]
        charttype = 'bar'

    elif report == 'usermonth':
        title = _('User by Month')
        col1heading = _('User')
        possible_options = periods
        charttype = 'date'

    elif report == 'queuepriority':
        title = _('Queue by Priority')
        col1heading = _('Queue')
        possible_options = [t[1].title() for t in Ticket.PRIORITY_CHOICES]
        charttype = 'bar'

    elif report == 'queuestatus':
        title = _('Queue by Status')
        col1heading = _('Queue')
        possible_options = [s[1].title() for s in Ticket.STATUS_CHOICES]
        charttype = 'bar'

    elif report == 'queuemonth':
        title = _('Queue by Month')
        col1heading = _('Queue')
        possible_options = periods
        charttype = 'date'

    elif report == 'daysuntilticketclosedbymonth':
        title = _('Days until ticket closed by Month')
        col1heading = _('Queue')
        possible_options = periods
        charttype = 'date'
    update_summary_tables(report_queryset, report, summarytable, summarytable2)
    if report == 'daysuntilticketclosedbymonth':
        for key in summarytable2.keys():
            summarytable[key] = summarytable2[key] / summarytable[key]

    header1 = sorted(set(list(i for i, _ in summarytable.keys())))

    column_headings = [col1heading] + possible_options

    # Prepare a dict to store totals for each possible option
    table, totals = get_report_table_and_totals(header1, summarytable, possible_options)
    # Pivot the data so that 'header1' fields are always first column
    # in the row, and 'possible_options' are always the 2nd - nth columns.

    # Zip data and headers together in one list for Morris.js charts
    # will get a list like [(Header1, Data1), (Header2, Data2)...]
    seriesnum = 0
    morrisjs_data = []
    for label in column_headings[1:]:
        seriesnum += 1
        datadict = {"x": label}
        for n in range(0, len(table)):
            datadict[n] = table[n][seriesnum]
        morrisjs_data.append(datadict)

    series_names = []
    for series in table:
        series_names.append(series[0])

    # Add total row to table
    total_data = ['Total']
    for hdr in possible_options:
        total_data.append(str(totals[hdr]))

    return render(request, 'helpdesk/report_output.html', {
        'title': title,
        'charttype': charttype,
        'data': table,
        'total_data': total_data,
        'headings': column_headings,
        'series_names': series_names,
        'morrisjs_data': morrisjs_data,
        'from_saved_query': saved_query is not None,
        'saved_query': saved_query,
    })


run_report = staff_member_required(run_report)


@helpdesk_staff_member_required
def save_query(request):
    title = request.POST.get('title', None)
    shared = request.POST.get('shared', False)
    if shared == 'on':  # django only translates '1', 'true', 't' into True
        shared = True
    query_encoded = request.POST.get('query_encoded', None)

    if not title or not query_encoded:
        return HttpResponseRedirect(reverse('helpdesk:list'))

    query = SavedSearch(title=title, shared=shared,
                        query=query_encoded, user=request.user)
    query.save()

    return HttpResponseRedirect('%s?saved_query=%s' % (reverse('helpdesk:list'), query.id))


save_query = staff_member_required(save_query)


@helpdesk_staff_member_required
def delete_saved_query(request, pk):
    query = get_object_or_404(SavedSearch, id=pk, user=request.user)

    if request.method == 'POST':
        query.delete()
        return HttpResponseRedirect(reverse('helpdesk:list'))
    else:
        return render(request, 'helpdesk/confirm_delete_saved_query.html', {'query': query})


delete_saved_query = staff_member_required(delete_saved_query)


class EditUserSettingsView(MustBeStaffMixin, UpdateView):
    template_name = 'helpdesk/user_settings.html'
    form_class = UserSettingsForm
    model = UserSettings
    success_url = reverse_lazy('helpdesk:dashboard')

    def get_object(self, queryset=None):
        return UserSettings.objects.get_or_create(user=self.request.user)[0]


@helpdesk_superuser_required
def email_ignore(request):
    return render(request, 'helpdesk/email_ignore_list.html', {
        'ignore_list': IgnoreEmail.objects.all(),
    })


email_ignore = superuser_required(email_ignore)


@helpdesk_superuser_required
def email_ignore_add(request):
    if request.method == 'POST':
        form = EmailIgnoreForm(request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('helpdesk:email_ignore'))
    else:
        form = EmailIgnoreForm(request.GET)

    return render(request, 'helpdesk/email_ignore_add.html', {'form': form})


email_ignore_add = superuser_required(email_ignore_add)


@helpdesk_superuser_required
def email_ignore_del(request, pk):
    ignore = get_object_or_404(IgnoreEmail, id=pk)
    if request.method == 'POST':
        ignore.delete()
        return HttpResponseRedirect(reverse('helpdesk:email_ignore'))
    else:
        return render(request, 'helpdesk/email_ignore_del.html', {'ignore': ignore})


email_ignore_del = superuser_required(email_ignore_del)


@helpdesk_staff_member_required
def ticket_cc(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    copies_to = ticket.ticketcc_set.all()
    return render(request, 'helpdesk/ticket_cc_list.html', {
        'copies_to': copies_to,
        'ticket': ticket,
    })


ticket_cc = staff_member_required(ticket_cc)


@helpdesk_staff_member_required
def ticket_cc_add(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    form = None
    if request.method == 'POST':
        form = TicketCCForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data.get('user')
            email = form.cleaned_data.get('email')
            if user and ticket.ticketcc_set.filter(user=user).exists():
                form.add_error(
                    'user', _('Impossible to add twice the same user'))
            elif email and ticket.ticketcc_set.filter(email=email).exists():
                form.add_error('email', _(
                    'Impossible to add twice the same email address'))
            else:
                ticketcc = form.save(commit=False)
                ticketcc.ticket = ticket
                ticketcc.save()
                return HttpResponseRedirect(reverse('helpdesk:ticket_cc', kwargs={'ticket_id': ticket.id}))

    return render(request, 'helpdesk/ticket_cc_add.html', {
        'ticket': ticket,
        'form': form,
        'form_email': TicketCCEmailForm(),
        'form_user': TicketCCUserForm(),
    })


ticket_cc_add = staff_member_required(ticket_cc_add)


@helpdesk_staff_member_required
def ticket_cc_del(request, ticket_id, cc_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    cc = get_object_or_404(TicketCC, ticket__id=ticket_id, id=cc_id)

    if request.method == 'POST':
        cc.delete()
        return HttpResponseRedirect(reverse('helpdesk:ticket_cc', kwargs={'ticket_id': cc.ticket.id}))

    return render(request, 'helpdesk/ticket_cc_del.html', {'ticket': ticket, 'cc': cc})


ticket_cc_del = staff_member_required(ticket_cc_del)


@helpdesk_staff_member_required
def ticket_dependency_add(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)
    if request.method == 'POST':
        form = TicketDependencyForm(ticket, request.POST)
        if form.is_valid():
            ticketdependency = form.save(commit=False)
            ticketdependency.ticket = ticket
            if ticketdependency.ticket != ticketdependency.depends_on:
                ticketdependency.save()
            return redirect(ticket.get_absolute_url())
    else:
        form = TicketDependencyForm(ticket)
    return render(request, 'helpdesk/ticket_dependency_add.html', {
        'ticket': ticket,
        'form': form,
    })


ticket_dependency_add = staff_member_required(ticket_dependency_add)


@helpdesk_staff_member_required
def ticket_dependency_del(request, ticket_id, dependency_id):
    dependency = get_object_or_404(
        TicketDependency, ticket__id=ticket_id, id=dependency_id)
    if request.method == 'POST':
        dependency.delete()
        return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket_id]))
    return render(request, 'helpdesk/ticket_dependency_del.html', {'dependency': dependency})


ticket_dependency_del = staff_member_required(ticket_dependency_del)


@helpdesk_staff_member_required
def ticket_resolves_add(request, ticket_id):
    depends_on = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, depends_on)
    if request.method == 'POST':
        form = TicketResolvesForm(depends_on, request.POST)
        if form.is_valid():
            ticketdependency = form.save(commit=False)
            ticketdependency.depends_on = depends_on
            if ticketdependency.ticket != ticketdependency.depends_on:
                ticketdependency.save()
            return redirect(depends_on.get_absolute_url())
    else:
        form = TicketResolvesForm(depends_on)
    return render(request, 'helpdesk/ticket_resolves_add.html', {
        'depends_on': depends_on,
        'form': form,
    })


ticket_resolves_add = staff_member_required(ticket_resolves_add)

        
@helpdesk_staff_member_required
def ticket_resolves_del(request, ticket_id, dependency_id):
    dependency = get_object_or_404(
        TicketDependency, ticket__id=ticket_id, id=dependency_id)
    depends_on_id = dependency.depends_on.id
    if request.method == 'POST':
        dependency.delete()
        return HttpResponseRedirect(reverse('helpdesk:view', args=[depends_on_id]))
    return render(request, 'helpdesk/ticket_dependency_del.html', {'dependency': dependency})

ticket_resolves_del = staff_member_required(ticket_resolves_del)


@helpdesk_staff_member_required
def attachment_del(request, ticket_id, attachment_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    attachment = get_object_or_404(FollowUpAttachment, id=attachment_id)
    if request.method == 'POST':
        attachment.delete()
        return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket_id]))
    return render(request, 'helpdesk/ticket_attachment_del.html', {
        'attachment': attachment,
        'filename': attachment.filename,
    })


def calc_average_nbr_days_until_ticket_resolved(Tickets):
    nbr_closed_tickets = len(Tickets)
    days_per_ticket = 0
    days_each_ticket = list()

    for ticket in Tickets:
        time_ticket_open = ticket.modified - ticket.created
        days_this_ticket = time_ticket_open.days
        days_per_ticket += days_this_ticket
        days_each_ticket.append(days_this_ticket)

    if nbr_closed_tickets > 0:
        mean_per_ticket = days_per_ticket / nbr_closed_tickets
    else:
        mean_per_ticket = 0

    return mean_per_ticket


def calc_basic_ticket_stats(Tickets):
    # all not closed tickets (open, reopened, resolved,) - independent of user
    all_open_tickets = Tickets.exclude(status=Ticket.CLOSED_STATUS)
    today = datetime.today()

    date_30 = date_rel_to_today(today, 30)
    date_60 = date_rel_to_today(today, 60)
    date_30_str = date_30.strftime(CUSTOMFIELD_DATE_FORMAT)
    date_60_str = date_60.strftime(CUSTOMFIELD_DATE_FORMAT)

    # > 0 & <= 30
    ota_le_30 = all_open_tickets.filter(created__gte=date_30_str)
    N_ota_le_30 = len(ota_le_30)

    # >= 30 & <= 60
    ota_le_60_ge_30 = all_open_tickets.filter(
        created__gte=date_60_str, created__lte=date_30_str)
    N_ota_le_60_ge_30 = len(ota_le_60_ge_30)

    # >= 60
    ota_ge_60 = all_open_tickets.filter(created__lte=date_60_str)
    N_ota_ge_60 = len(ota_ge_60)

    # (O)pen (T)icket (S)tats
    ots = list()
    # label, number entries, color, sort_string
    ots.append(['Tickets < 30 days', N_ota_le_30, 'success',
                sort_string(date_30_str, ''), ])
    ots.append(['Tickets 30 - 60 days', N_ota_le_60_ge_30,
                'success' if N_ota_le_60_ge_30 == 0 else 'warning',
                sort_string(date_60_str, date_30_str), ])
    ots.append(['Tickets > 60 days', N_ota_ge_60,
                'success' if N_ota_ge_60 == 0 else 'danger',
                sort_string('', date_60_str), ])

    # all closed tickets - independent of user.
    all_closed_tickets = Tickets.filter(status=Ticket.CLOSED_STATUS)
    average_nbr_days_until_ticket_closed = \
        calc_average_nbr_days_until_ticket_resolved(all_closed_tickets)
    # all closed tickets that were opened in the last 60 days.
    all_closed_last_60_days = all_closed_tickets.filter(
        created__gte=date_60_str)
    average_nbr_days_until_ticket_closed_last_60_days = \
        calc_average_nbr_days_until_ticket_resolved(all_closed_last_60_days)

    # put together basic stats
    basic_ticket_stats = {
        'average_nbr_days_until_ticket_closed': average_nbr_days_until_ticket_closed,
        'average_nbr_days_until_ticket_closed_last_60_days':
            average_nbr_days_until_ticket_closed_last_60_days,
        'open_ticket_stats': ots,
    }

    return basic_ticket_stats


def get_color_for_nbr_days(nbr_days):
    if nbr_days < 5:
        color_string = 'green'
    elif nbr_days < 10:
        color_string = 'orange'
    else:  # more than 10 days
        color_string = 'red'

    return color_string


def days_since_created(today, ticket):
    return (today - ticket.created).days


def date_rel_to_today(today, offset):
    return today - timedelta(days=offset)


def sort_string(begin, end):
    return 'sort=created&date_from=%s&date_to=%s&status=%s&status=%s&status=%s' % (
        begin, end, Ticket.OPEN_STATUS, Ticket.REOPENED_STATUS, Ticket.RESOLVED_STATUS)


@helpdesk_staff_member_required
def checklist_templates(request, checklist_template_id=None):
    checklist_template = None
    if checklist_template_id:
        checklist_template = get_object_or_404(ChecklistTemplate, id=checklist_template_id)
    form = ChecklistTemplateForm(request.POST or None, instance=checklist_template)
    if form.is_valid():
        form.save()
        return redirect('helpdesk:checklist_templates')
    return render(request, 'helpdesk/checklist_templates.html', {
        'checklists': ChecklistTemplate.objects.all(),
        'checklist_template': checklist_template,
        'form': form
    })


@helpdesk_staff_member_required
def delete_checklist_template(request, checklist_template_id):
    checklist_template = get_object_or_404(ChecklistTemplate, id=checklist_template_id)
    if request.method == 'POST':
        checklist_template.delete()
        return redirect('helpdesk:checklist_templates')
    return render(request, 'helpdesk/checklist_template_confirm_delete.html', {
        'checklist_template': checklist_template,
    })
