"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2026 Jutda. All Rights Reserved. See LICENSE for details.

views/staff.py - The bulk of the application - provides most business logic and
                 renders all staff-facing views.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.views import redirect_to_login
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.handlers.wsgi import WSGIRequest
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Case, F, Q, When
from django.forms import HiddenInput, TextInput, inlineformset_factory
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.html import escape
from django.utils.timezone import now
from django.utils.translation import gettext as _
from django.views.decorators.csrf import requires_csrf_token
from django.views.generic.edit import FormView, UpdateView
from rest_framework import status
from rest_framework.decorators import api_view

from helpdesk import settings as helpdesk_settings
from helpdesk.decorators import (
    helpdesk_staff_member_required,
    helpdesk_superuser_required,
    is_helpdesk_staff,
    superuser_required,
)
from helpdesk.forms import (
    CUSTOMFIELD_DATE_FORMAT,
    ChecklistForm,
    ChecklistTemplateForm,
    CreateChecklistForm,
    EditFollowUpForm,
    EditTicketCustomFieldForm,
    EditTicketForm,
    EmailIgnoreForm,
    FormControlDeleteFormSet,
    MultipleTicketSelectForm,
    TicketCCEmailForm,
    TicketCCForm,
    TicketCCUserForm,
    TicketDependencyForm,
    TicketForm,
    TicketResolvesForm,
    UserSettingsForm,
)
from helpdesk.lib import (
    get_assignable_users,
    queue_template_context,
    safe_template_context,
)
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
    TicketChange,
    TicketCustomFieldValue,
    TicketDependency,
    UserSettings,
)
from helpdesk.query import get_query_class, query_from_base64, query_to_base64
from helpdesk.sanitize import preview_csp, sanitize_email_html, sanitizer_available
from helpdesk.update_ticket import (
    return_ticketccstring_and_show_subscribe,
    subscribe_to_ticket_updates,
    update_ticket,
)
from helpdesk.user import HelpdeskUser
from helpdesk.views import abstract_views
from helpdesk.views.permissions import MustBeStaffMixin

from ..lib import format_time_spent
from ..templated_email import send_templated_mail

if helpdesk_settings.HELPDESK_KB_ENABLED:
    from helpdesk.models import KBItem


DATE_RE: re.Pattern = re.compile(
    r"(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{4})$"
)

User = get_user_model()
Query = get_query_class()

if helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE:
    # treat 'normal' users like 'staff'
    staff_member_required = user_passes_test(
        lambda u: u.is_authenticated and u.is_active
    )
else:
    staff_member_required = user_passes_test(
        lambda u: u.is_authenticated and u.is_active and u.is_staff
    )


def _get_queue_choices(queues):
    """Return list of `choices` array for html form for given queues

    idea is to return only one choice if there is only one queue or add empty
    choice at the beginning of the list, if there are more queues
    """
    queue_choices = []
    if len(queues) > 1:
        queue_choices = [("", "--------")]
    queue_choices += [(q.id, q.title) for q in queues]
    return queue_choices


def get_user_queues(user) -> dict[str, str]:
    queues = HelpdeskUser(user).get_queues()
    return _get_queue_choices(queues)


def get_form_extra_kwargs(user) -> dict[str, object]:
    return {
        "assignable_users": get_assignable_users(
            helpdesk_settings.HELPDESK_STAFF_ONLY_TICKET_OWNERS
        ),
        "queues": get_user_queues(user),
        "priorities": Ticket.PRIORITY_CHOICES,
    }


# Sort keys the dashboard templates actually emit (see
# templates/helpdesk/include/tickets.html and include/unassigned.html),
# optionally prefixed with "-" for a descending sort. These values land
# straight in order_by(), so anything else has to be dropped: an unvalidated
# key lets a sort traverse arbitrary relations (e.g. ?una_sort=queue__email_box_pass
# orders the unassigned tickets by a queue's plaintext mailbox password),
# turning row ordering into a side channel over unrelated tables.
DASHBOARD_ALLOWED_SORTS = {
    "created",
    "id",
    "modified",
    "priority",
    "queue",
    "status",
}

DASHBOARD_DEFAULT_SORT = "-created"


def get_dashboard_sort(request, param, default=DASHBOARD_DEFAULT_SORT):
    """
    Read a dashboard sort parameter from the query string and only return it if
    it is on the allowlist, falling back to `default` otherwise. Silently
    falling back rather than raising keeps a stale bookmark or a customised
    template from breaking the page, and matches how ticket_list() already
    handles its own `sort` parameter.
    """
    sorting = request.GET.get(param) or default
    field = sorting.removeprefix("-")
    if field not in DASHBOARD_ALLOWED_SORTS:
        return default
    return sorting


@helpdesk_staff_member_required
def dashboard(request):
    """
    A quick summary overview for users: A list of their own tickets, a table
    showing ticket counts by queue/status, and a list of unassigned tickets
    with options for them to 'Take' ownership of said tickets.
    """
    # user settings num tickets per page
    if request.user.is_authenticated and hasattr(request.user, "usersettings_helpdesk"):
        tickets_per_page = request.user.usersettings_helpdesk.tickets_per_page
    else:
        tickets_per_page = 25

    # page vars for the four ticket tables
    user_tickets_page = request.GET.get(_("ut_page"), 1)
    user_tickets_closed_resolved_page = request.GET.get(_("utcr_page"), 1)
    all_tickets_reported_by_current_user_page = request.GET.get(_("atrbcu_page"), 1)
    unassigned_tickets_page = request.GET.get(_("una_page"), 1)

    # sorting parameters for each table
    user_tickets_sort = get_dashboard_sort(request, "ut_sort")
    user_tickets_closed_sort = get_dashboard_sort(request, "utcr_sort")
    all_tickets_reported_sort = get_dashboard_sort(request, "atrbcu_sort")
    unassigned_tickets_sort = get_dashboard_sort(request, "una_sort")

    huser = HelpdeskUser(request.user)
    active_tickets = Ticket.objects.select_related("queue").exclude(
        status__in=[
            Ticket.CLOSED_STATUS,
            Ticket.RESOLVED_STATUS,
            Ticket.DUPLICATE_STATUS,
        ],
    )

    # open & reopened tickets, assigned to current user
    tickets = active_tickets.filter(
        assigned_to=request.user,
    ).order_by(user_tickets_sort)

    # closed & resolved tickets, assigned to current user
    tickets_closed_resolved = (
        Ticket.objects.select_related("queue")
        .filter(
            assigned_to=request.user,
            status__in=[
                Ticket.CLOSED_STATUS,
                Ticket.RESOLVED_STATUS,
                Ticket.DUPLICATE_STATUS,
            ],
        )
        .order_by(user_tickets_closed_sort)
    )

    user_queues = huser.get_queues()

    unassigned_tickets = active_tickets.filter(
        assigned_to__isnull=True, queue__in=user_queues
    ).order_by(unassigned_tickets_sort)
    kbitems = None
    # Teams mode uses assignment via knowledge base items so exclude tickets assigned to KB items
    if helpdesk_settings.HELPDESK_TEAMS_MODE_ENABLED:
        unassigned_tickets = unassigned_tickets.filter(kbitem__isnull=True)
        kbitems = huser.get_assigned_kb_items()

    # all tickets, reported by current user
    all_tickets_reported_by_current_user = ""
    email_current_user = request.user.email
    if email_current_user:
        all_tickets_reported_by_current_user = (
            Ticket.objects.select_related("queue")
            .filter(
                submitter_email=email_current_user,
            )
            .order_by(all_tickets_reported_sort)
        )

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
    paginator = Paginator(tickets, tickets_per_page)
    try:
        tickets = paginator.page(user_tickets_page)
    except PageNotAnInteger:
        tickets = paginator.page(1)
    except EmptyPage:
        tickets = paginator.page(paginator.num_pages)

    # get user completed tickets page
    paginator = Paginator(tickets_closed_resolved, tickets_per_page)
    try:
        tickets_closed_resolved = paginator.page(user_tickets_closed_resolved_page)
    except PageNotAnInteger:
        tickets_closed_resolved = paginator.page(1)
    except EmptyPage:
        tickets_closed_resolved = paginator.page(paginator.num_pages)

    # get user submitted tickets page
    paginator = Paginator(all_tickets_reported_by_current_user, tickets_per_page)
    try:
        all_tickets_reported_by_current_user = paginator.page(
            all_tickets_reported_by_current_user_page
        )
    except PageNotAnInteger:
        all_tickets_reported_by_current_user = paginator.page(1)
    except EmptyPage:
        all_tickets_reported_by_current_user = paginator.page(paginator.num_pages)

    # get unassigned tickets page
    paginator = Paginator(unassigned_tickets, tickets_per_page)
    try:
        unassigned_tickets = paginator.page(unassigned_tickets_page)
    except PageNotAnInteger:
        unassigned_tickets = paginator.page(1)
    except EmptyPage:
        unassigned_tickets = paginator.page(paginator.num_pages)

    return render(
        request,
        "helpdesk/dashboard.html",
        {
            "user_tickets": tickets,
            "user_tickets_closed_resolved": tickets_closed_resolved,
            "unassigned_tickets": unassigned_tickets,
            "kbitems": kbitems,
            "all_tickets_reported_by_current_user": all_tickets_reported_by_current_user,
            "basic_ticket_stats": basic_ticket_stats,
            "user_tickets_sort": user_tickets_sort,
            "user_tickets_closed_sort": user_tickets_closed_sort,
            "all_tickets_reported_sort": all_tickets_reported_sort,
            "unassigned_tickets_sort": unassigned_tickets_sort,
        },
    )


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

    if request.method == "GET":
        return render(
            request,
            "helpdesk/delete_ticket.html",
            {"ticket": ticket, "next": request.GET.get("next", "home")},
        )
    else:
        ticket.delete()
        redirect_to = "helpdesk:home"
        if request.POST.get("next") == "dashboard":
            redirect_to = "helpdesk:dashboard"
        return HttpResponseRedirect(reverse(redirect_to))


delete_ticket = staff_member_required(delete_ticket)


@helpdesk_staff_member_required
def followup_edit(request, ticket_id, followup_id):
    """Edit followup options with an ability to change the ticket."""
    followup = get_object_or_404(FollowUp, id=followup_id)
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    if request.method == "GET":
        form = EditFollowUpForm(
            initial={
                "title": escape(followup.title),
                "ticket": followup.ticket,
                "comment": escape(followup.comment),
                "public": followup.public,
                "new_status": followup.new_status,
                "time_spent": format_time_spent(followup.time_spent),
            }
        )

        # Modify the ticket field queryset to include current ticket + all open tickets
        if ticket.status not in Ticket.OPEN_STATUSES:
            # If current ticket is closed, add it to the queryset
            form.fields["ticket"].queryset = (
                Ticket.objects.filter(
                    Q(id=ticket.id) | Q(status__in=Ticket.OPEN_STATUSES)
                )
                .distinct()
                .order_by("-id")
            )
        else:
            # If ticket is open, just show open tickets
            form.fields["ticket"].queryset = Ticket.objects.filter(
                status__in=Ticket.OPEN_STATUSES
            ).order_by("-id")

        ticketcc_string = return_ticketccstring_and_show_subscribe(
            request.user, ticket
        )[0]
        return render(
            request,
            "helpdesk/followup_edit.html",
            {
                "followup": followup,
                "ticket": ticket,
                "form": form,
                "ticketcc_string": ticketcc_string,
                "ticket_attachments": get_attachments_for_ticket(ticket),
            },
        )
    elif request.method == "POST":
        form = EditFollowUpForm(request.POST)

        # Needed to allow editing of closed tickets followups
        original_ticket = get_object_or_404(Ticket, id=followup.ticket.id)
        if original_ticket.status not in Ticket.OPEN_STATUSES:
            form.fields["ticket"].queryset = Ticket.objects.filter(
                Q(id=original_ticket.id) | Q(status__in=Ticket.OPEN_STATUSES)
            ).distinct()

        if form.is_valid():
            # Edit in place: a copy would lose the message ID and the
            # TicketChange rows, which cascade away with the old row.
            followup.title = form.cleaned_data["title"]
            followup.ticket = form.cleaned_data["ticket"]
            followup.comment = form.cleaned_data["comment"]
            followup.public = form.cleaned_data["public"]
            followup.new_status = form.cleaned_data["new_status"]
            followup.time_spent = form.cleaned_data["time_spent"]
            followup.save()
            return HttpResponseRedirect(reverse("helpdesk:view", args=[ticket.id]))


followup_edit = staff_member_required(followup_edit)


@helpdesk_staff_member_required
def followup_delete(request, ticket_id, followup_id):
    """followup delete for superuser"""

    ticket = get_object_or_404(Ticket, id=ticket_id)
    if not request.user.is_superuser:
        return HttpResponseRedirect(reverse("helpdesk:view", args=[ticket.id]))

    followup = get_object_or_404(FollowUp, id=followup_id)
    followup.delete()
    return HttpResponseRedirect(reverse("helpdesk:view", args=[ticket.id]))


followup_delete = staff_member_required(followup_delete)


def get_followups_for_ticket(ticket):
    """Returns the ticket's follow ups, ordered per HELPDESK_FOLLOWUP_NEWEST_FIRST."""
    order = "-date" if helpdesk_settings.HELPDESK_FOLLOWUP_NEWEST_FIRST else "date"
    return ticket.followup_set.order_by(order)


def get_attachments_for_ticket(ticket):
    """Returns all of the ticket's attachments across its follow ups, most recent first."""
    return (
        FollowUpAttachment.objects.filter(followup__ticket=ticket)
        .select_related("followup")
        .order_by("-id")
    )


@helpdesk_staff_member_required
def view_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    try:
        ticket_perm_check(request, ticket)
    except PermissionDenied:
        messages.error(
            request,
            _("You don't have permission to view ticket - %(ticket)s.")
            % {"ticket": str(ticket)},
        )
        return HttpResponseRedirect(reverse("helpdesk:list"))

    if "take" in request.GET:
        update_ticket(request.user, ticket, owner=request.user.id)
        return return_to_ticket(request.user, ticket)

    if "subscribe" in request.GET:
        # Allow the user to subscribe him/herself to the ticket whilst viewing
        # it.
        show_subscribe = return_ticketccstring_and_show_subscribe(request.user, ticket)[
            1
        ]

        if show_subscribe:
            subscribe_to_ticket_updates(ticket, request.user.id)
            return HttpResponseRedirect(reverse("helpdesk:view", args=[ticket.id]))

    if "close" in request.GET and ticket.status == Ticket.RESOLVED_STATUS:
        if not ticket.assigned_to:
            owner = 0
        else:
            owner = ticket.assigned_to.id

        update_ticket(
            request.user,
            ticket,
            owner=owner,
            comment=_("Accepted resolution and closed ticket"),
        )
        return return_to_ticket(request.user, ticket)

    extra_context_kwargs = get_form_extra_kwargs(request.user)
    form = TicketForm(
        initial={"due_date": ticket.due_date},
        queue_choices=extra_context_kwargs["queues"],
    )
    ticketcc_string, show_subscribe = return_ticketccstring_and_show_subscribe(
        request.user, ticket
    )

    submitter_userprofile = ticket.get_submitter_userprofile()
    if submitter_userprofile is not None:
        content_type = ContentType.objects.get_for_model(submitter_userprofile)
        submitter_userprofile_url = reverse(
            f"admin:{content_type.app_label}_{content_type.model}_change",
            kwargs={"object_id": submitter_userprofile.id},
        )
    else:
        submitter_userprofile_url = None

    checklist_form = CreateChecklistForm(request.POST or None)
    if checklist_form.is_valid():
        checklist = checklist_form.save(commit=False)
        checklist.ticket = ticket
        checklist.save()

        checklist_template = checklist_form.cleaned_data.get("checklist_template")
        # Add predefined tasks if template has been selected
        if checklist_template:
            checklist.create_tasks_from_template(checklist_template)

        return redirect("helpdesk:edit_ticket_checklist", ticket.id, checklist.id)

    # List open tickets on top
    dependencies = ticket.ticketdependency.annotate(
        rank=Case(When(depends_on__status__in=Ticket.OPEN_STATUSES, then=1), default=2)
    ).order_by("rank")

    # add custom fields to further details panel
    customfields_form = EditTicketCustomFieldForm(None, instance=ticket)

    return render(
        request,
        "helpdesk/ticket.html",
        {
            "ticket": ticket,
            "followups": get_followups_for_ticket(ticket),
            "dependencies": dependencies,
            "ticket_attachments": get_attachments_for_ticket(ticket),
            "submitter_userprofile_url": submitter_userprofile_url,
            "form": form,
            "preset_replies": PreSetReply.objects.filter(
                Q(queues=ticket.queue) | Q(queues__isnull=True)
            ),
            "ticketcc_string": ticketcc_string,
            "SHOW_SUBSCRIBE": show_subscribe,
            "checklist_form": checklist_form,
            "customfields_form": customfields_form,
            "assignable_users": get_assignable_users(
                helpdesk_settings.HELPDESK_STAFF_ONLY_TICKET_OWNERS
            ),
            **extra_context_kwargs,
        },
    )


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
        fields=["description", "position"],
        widgets={
            "position": HiddenInput(),
            "description": TextInput(attrs={"class": "form-control"}),
        },
        can_delete=True,
        extra=0,
    )
    formset = TaskFormSet(request.POST or None, instance=checklist)
    if form.is_valid() and formset.is_valid():
        form.save()
        formset.save()
        return redirect(ticket)

    return render(
        request,
        "helpdesk/checklist_form.html",
        {
            "ticket": ticket,
            "checklist": checklist,
            "form": form,
            "formset": formset,
        },
    )


@helpdesk_staff_member_required
def delete_ticket_checklist(request, ticket_id, checklist_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)
    checklist = get_object_or_404(ticket.checklists.all(), id=checklist_id)

    if request.method == "POST":
        checklist.delete()
        return redirect(ticket)

    return render(
        request,
        "helpdesk/checklist_confirm_delete.html",
        {
            "ticket": ticket,
            "checklist": checklist,
        },
    )


def get_ticket_from_request_with_authorisation(
    request: WSGIRequest, ticket_id: str, public: bool
) -> Ticket:
    """Gets a ticket from the public status and if the user is authenticated and
    has permissions to update tickets

    Raises:
        Http404 when the ticket can not be found or the user lacks permission

    """
    if not (
        public
        or (
            request.user.is_authenticated
            and request.user.is_active
            and (
                is_helpdesk_staff(request.user)
                or helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE
            )
        )
    ):
        try:
            return Ticket.objects.get(
                id=ticket_id,
                submitter_email__iexact=request.POST.get("mail"),
                secret_key__iexact=request.POST.get("key"),
            )
        except (Ticket.DoesNotExist, ValueError):
            raise PermissionDenied()

    return get_object_or_404(Ticket, id=ticket_id)


def get_due_date_from_form_or_ticket(form, ticket: Ticket) -> datetime.date | None:
    """Tries to locate the due date for a ticket from the form
    'due_date' parameter or the `due_date_*` paramaters.
    """
    due_date = form.cleaned_data.get("due_date") or None
    if due_date is None:
        due_date_year = int(form.cleaned_data.get("due_date_year", 0))
        due_date_month = int(form.cleaned_data.get("due_date_month", 0))
        due_date_day = int(form.cleaned_data.get("due_date_day", 0))
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
                due_date = due_date.replace(due_date_year, due_date_month, due_date_day)
    return due_date


def get_time_spent_from_form(form: dict) -> timedelta | None:
    if form.data.get("time_spent"):
        (hours, minutes) = [int(f) for f in form.data.get("time_spent").split(":")]
        return timedelta(hours=hours, minutes=minutes)
    return None


def update_ticket_view(request, ticket_id, *args, **kwargs):
    return UpdateTicketView.as_view()(request, *args, ticket_id=ticket_id, **kwargs)


def save_ticket_update(form, ticket, user):
    comment = form.data.get("comment", "")
    new_status = int(form.data.get("new_status", ticket.status))
    title = form.cleaned_data.get("title", ticket.title)
    owner = int(form.data.get("owner", -1))
    priority = int(form.cleaned_data.get("priority", ticket.priority))
    queue = int(form.cleaned_data.get("queue", ticket.queue.id))

    # custom fields
    customfields_form = EditTicketCustomFieldForm(
        form.cleaned_data or None, instance=ticket
    )

    # Check if a change happened on checklists
    new_checklists = {}
    changes_in_checklists = False
    for checklist in ticket.checklists.all():
        old_completed = set(checklist.tasks.completed().values_list("id", flat=True))
        # Checklists will not be in the cleaned_data so access the submitted data
        new_checklist = set(
            map(int, form.data.getlist(f"checklist-{checklist.id}", []))
        )
        new_checklists[checklist.id] = new_checklist
        if new_checklist != old_completed:
            changes_in_checklists = True

    # NOTE: jQuery's default for dates is mm/dd/yy
    # very US-centric but for now that's the only format supported
    # until we clean up code to internationalize a little more
    due_date = get_due_date_from_form_or_ticket(form, ticket)
    no_changes = all(
        [
            not form.files,
            not comment,
            not changes_in_checklists,
            new_status == ticket.status,
            title == ticket.title,
            priority == int(ticket.priority),
            queue == int(ticket.queue.id),
            due_date == ticket.due_date,
            (owner == -1)
            or (not owner and not ticket.assigned_to)
            or (owner and User.objects.get(id=owner) == ticket.assigned_to),
            not customfields_form.has_changed(),
        ]
    )
    if no_changes:
        return ticket

    update_ticket(
        user,
        ticket,
        title=title,
        comment=comment,
        files=form.files.getlist("attachment"),
        public=form.data.get("public", False),
        owner=owner,
        priority=priority,
        queue=queue,
        new_status=new_status,
        time_spent=get_time_spent_from_form(form),
        due_date=due_date,
        new_checklists=new_checklists,
        customfields_form=customfields_form,
    )

    return ticket


def return_to_ticket(user, ticket):
    """Helper function for update_ticket"""

    if is_helpdesk_staff(user):
        return HttpResponseRedirect(ticket.get_absolute_url())
    else:
        return HttpResponseRedirect(ticket.ticket_url)


@helpdesk_staff_member_required
def mass_update(request):
    tickets = request.POST.getlist("ticket_id")
    action = request.POST.get("action", None)
    if not (tickets and action):
        return HttpResponseRedirect(reverse("helpdesk:list"))

    user = kbitem = None

    if action.startswith("assign_"):
        parts = action.split("_")
        user = User.objects.get(id=parts[1])
        action = "assign"
    if action == "kbitem_none":
        action = "set_kbitem"
    if action.startswith("kbitem_"):
        parts = action.split("_")
        kbitem = KBItem.objects.get(id=parts[1])
        action = "set_kbitem"
    elif action == "take":
        user = request.user
        action = "assign"
    elif action == "merge":
        # Redirect to the Merge View with selected tickets id in the GET
        # request
        return redirect(
            reverse("helpdesk:merge_tickets")
            + "?"
            + "&".join([f"tickets={ticket_id}" for ticket_id in tickets])
        )

    huser = HelpdeskUser(request.user)
    for t in Ticket.objects.filter(id__in=tickets):
        if not huser.can_access_queue(t.queue):
            continue

        if action == "assign" and t.assigned_to != user:
            t.assigned_to = user
            t.save()
            t.followup_set.create(
                date=timezone.now(),
                title=_("Assigned to {username} in bulk update").format(
                    username=user.get_username()
                ),
                public=True,
                user=request.user,
            )
        elif action == "unassign" and t.assigned_to is not None:
            t.assigned_to = None
            t.save()
            t.followup_set.create(
                date=timezone.now(),
                title=_("Unassigned in bulk update"),
                public=True,
                user=request.user,
            )
        elif action == "set_kbitem":
            t.kbitem = kbitem
            t.save()
            t.followup_set.create(
                date=timezone.now(),
                title=_("KBItem set in bulk update"),
                public=False,
                user=request.user,
            )
        elif action == "close" and t.status != Ticket.CLOSED_STATUS:
            t.status = Ticket.CLOSED_STATUS
            t.save()
            t.followup_set.create(
                date=timezone.now(),
                title=_("Closed in bulk update"),
                public=False,
                user=request.user,
                new_status=Ticket.CLOSED_STATUS,
            )
        elif action == "close_public" and t.status != Ticket.CLOSED_STATUS:
            t.status = Ticket.CLOSED_STATUS
            t.save()
            t.followup_set.create(
                date=timezone.now(),
                title=_("Closed in bulk update"),
                public=True,
                user=request.user,
                new_status=Ticket.CLOSED_STATUS,
            )
            # Send email to Submitter, Owner, Queue CC
            context = safe_template_context(t)
            context.update(
                resolution=t.resolution, queue=queue_template_context(t.queue)
            )

            messages_sent_to = set()
            try:
                messages_sent_to.add(request.user.email)
            except AttributeError:
                pass

            roles = {
                "submitter": ("closed_submitter", context),
                "ticket_cc": ("closed_cc", context),
            }
            if (
                t.assigned_to
                and t.assigned_to.usersettings_helpdesk.email_on_ticket_change
            ):
                roles["assigned_to"] = ("closed_owner", context)

            messages_sent_to.update(
                t.send(
                    roles,
                    dont_send_to=messages_sent_to,
                    fail_silently=True,
                )
            )

        elif action == "delete":
            t.delete()

    return HttpResponseRedirect(reverse("helpdesk:list"))


mass_update = staff_member_required(mass_update)


# Prepare ticket attributes which will be displayed in the table to choose
# which value to keep when merging
TICKET_ATTRIBUTES = (
    ("created", _("Created date")),
    ("due_date", _("Due on")),
    ("get_status_display", _("Status")),
    ("submitter_email", _("Submitter email")),
    ("assigned_to", _("Owner")),
    ("description", _("Description")),
    ("resolution", _("Resolution")),
)


def merge_ticket_values(
    request: WSGIRequest, tickets: list[Ticket], custom_fields
) -> None:
    for ticket in tickets:
        ticket.values = {}
        # Prepare the value for each attributes of this ticket
        for attribute, __ in TICKET_ATTRIBUTES:
            value = getattr(ticket, attribute, TicketCustomFieldValue.default_value)
            # Check if attr is a get_FIELD_display
            if attribute.startswith("get_") and attribute.endswith("_display"):
                # Hack to call methods like get_FIELD_display()
                value = getattr(
                    ticket, attribute, TicketCustomFieldValue.default_value
                )()
            ticket.values[attribute] = {
                "value": value,
                "checked": str(ticket.id) == request.POST.get(attribute),
            }
        # Prepare the value for each custom fields of this ticket
        for custom_field in custom_fields:
            try:
                value = ticket.ticketcustomfieldvalue_set.get(field=custom_field).value
            except (TicketCustomFieldValue.DoesNotExist, ValueError):
                value = TicketCustomFieldValue.default_value
            ticket.values[custom_field.name] = {
                "value": value,
                "checked": str(ticket.id) == request.POST.get(custom_field.name),
            }


def redirect_from_chosen_ticket(
    request, chosen_ticket, tickets, custom_fields
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
            if attribute.startswith("get_") and attribute.endswith("_display"):
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
                selected_ticket = tickets.get(id=id_for_custom_field)
            except (Ticket.DoesNotExist, ValueError):
                continue

            # Check if the value for this ticket custom field
            # exists
            try:
                value = selected_ticket.ticketcustomfieldvalue_set.get(
                    field=custom_field
                ).value
            except TicketCustomFieldValue.DoesNotExist:
                continue

            # Create the custom field value or update it with the
            # value from the selected ticket
            custom_field_value, created = (
                chosen_ticket.ticketcustomfieldvalue_set.get_or_create(
                    field=custom_field, defaults={"value": value}
                )
            )
            if not created:
                custom_field_value.value = value
                custom_field_value.save(update_fields=["value"])
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
                template_name="merged",
                context=context,
                recipients=[ticket.submitter_email],
                bcc=[
                    cc.email_address
                    for cc in ticket.ticketcc_set.select_related("user")
                ],
                sender=ticket.queue.from_address,
                fail_silently=True,
            )

        # Move all followups and update their title to know they
        # come from another ticket
        ticket.followup_set.update(
            ticket=chosen_ticket,
            # Next might exceed maximum 200 characters limit
            title=_("[Merged from #%(id)d] %(title)s")
            % {"id": ticket.id, "title": ticket.title},
        )

        # Add submitter_email, assigned_to email and ticketcc to
        # chosen ticket if necessary
        chosen_ticket.add_email_to_ticketcc_if_not_in(email=ticket.submitter_email)
        if ticket.assigned_to and ticket.assigned_to.email:
            chosen_ticket.add_email_to_ticketcc_if_not_in(
                email=ticket.assigned_to.email
            )
        for ticketcc in ticket.ticketcc_set.all():
            chosen_ticket.add_email_to_ticketcc_if_not_in(ticketcc=ticketcc)
    return redirect(chosen_ticket)


@helpdesk_staff_member_required
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
        tickets = ticket_select_form.cleaned_data.get("tickets")

        huser = HelpdeskUser(request.user)
        for t in tickets:
            if not huser.can_access_queue(t.queue):
                raise PermissionDenied()

        custom_fields = CustomField.objects.all()

        merge_ticket_values(request, tickets, custom_fields)

        if request.method == "POST":
            # Find which ticket has been chosen to be the main one
            try:
                chosen_ticket = tickets.get(id=request.POST.get("chosen_ticket"))
            except Ticket.DoesNotExist:
                ticket_select_form.add_error(
                    field="tickets",
                    error=_(
                        "Please choose a ticket in which the others will be merged into."
                    ),
                )
            else:
                return redirect_from_chosen_ticket(
                    request, chosen_ticket, tickets, custom_fields
                )

    return render(
        request,
        "helpdesk/ticket_merge.html",
        {
            "tickets": tickets,
            "ticket_attributes": TICKET_ATTRIBUTES,
            "custom_fields": custom_fields,
            "ticket_select_form": ticket_select_form,
        },
    )


def check_redirect_on_user_query(request, huser):
    """If the user is coming from the header/navigation search box, lets' first
    look at their query to see if they have entered a valid ticket number. If
    they have, just redirect to that ticket number. Otherwise, we treat it as
    a keyword search.
    """
    if request.GET.get("search_type", None) == "header":
        query = request.GET.get("q")
        filter_ = None
        if query.find("-") > 0:
            try:
                queue, id_ = Ticket.queue_and_id_from_query(query)
                id_ = int(id_)
            except ValueError:
                pass
            else:
                filter_ = {"queue__slug": queue, "id": id_}
        else:
            try:
                query = int(query)
            except ValueError:
                pass
            else:
                filter_ = {"id": int(query)}

        if filter_:
            try:
                ticket = huser.get_tickets_in_queues().get(**filter_)
                return HttpResponseRedirect(ticket.staff_url)
            except Ticket.DoesNotExist:
                # Go on to standard keyword searching
                pass
    return None


@staff_member_required
@helpdesk_staff_member_required
def ticket_list(request: HttpRequest) -> HttpResponse:
    """
    Main ticket list view that shows a datatable with different filters.
    """

    huser = HelpdeskUser(request.user)

    # Query_params will hold a dictionary of parameters relating to
    # a query, to be saved if needed:
    query_params = {
        "filtering": {},
        "filtering_null": {},
        "sorting": None,
        "sortreverse": False,
        "search_string": "",
    }

    default_query_params = {
        "filtering": {
            "status__in": [1, 2],
        },
        "sorting": "created",
        "search_string": "",
        "sortreverse": False,
    }

    filter_in_params = [
        ("queue", "queue__id__in"),
        ("assigned_to", "assigned_to__id__in"),
        ("status", "status__in"),
        ("priority", "priority__in"),
        ("kbitem", "kbitem__in"),
    ]

    filter_null_params = {
        "queue": "queue__id__isnull",
        "assigned_to": "assigned_to__id__isnull",
        "status": "status__isnull",
        "priority": "priority__isnull",
        "kbitem": "kbitem__isnull",
    }

    ALLOWED_SORTS = {
        "status",
        "assigned_to",
        "created",
        "title",
        "queue",
        "priority",
        "last_followup",
        "kbitem",
        "id",
        "due_date",
        "submitter_email",
    }

    FILTERS = {
        "queue",
        "assigned_to",
        "status",
        "priority",
        "q",
        "sort",
        "sortreverse",
        "kbitem",
    }

    filters_applied = FILTERS.intersection(request.GET)

    # If searching from Nav bar search -> redirect to ticket detail
    redirect = check_redirect_on_user_query(request, huser)
    if redirect:
        return redirect

    try:
        saved_query, query_params = load_saved_query(request, query_params)
    except QueryLoadError:
        return HttpResponseRedirect(reverse("helpdesk:list"))

    if saved_query:
        pass

    elif not filters_applied:
        # Fall-back if no querying is being done
        query_params = deepcopy(default_query_params)

    else:
        for param, filter_command in filter_in_params:
            if request.GET.get(param) is not None:
                patterns = request.GET.getlist(param)
                if not patterns:
                    # Caters for the case where the filter is only a null filter
                    continue
                try:
                    minus_1_ndx = patterns.index("-1")
                    # Must have the value so remove it and configure to use OR filter on NULL
                    patterns.pop(minus_1_ndx)
                    query_params["filtering_null"][filter_null_params[param]] = True
                except ValueError:
                    pass
                try:
                    pattern_pks = [int(pattern) for pattern in patterns]
                    query_params["filtering"][filter_command] = pattern_pks
                except ValueError:
                    pass

        date_from = request.GET.get("date_from")
        if date_from:
            query_params["filtering"]["created__gte"] = date_from

        date_to = request.GET.get("date_to")
        if date_to:
            query_params["filtering"]["created__lte"] = date_to

        # KEYWORD SEARCHING
        query_params["search_string"] = request.GET.get("q", "")

        # SORTING
        sort = request.GET.get("sort", None)
        sortreverse = request.GET.get("sortreverse", None)
        query_params["sorting"] = sort if sort in ALLOWED_SORTS else "created"
        query_params["sortreverse"] = sortreverse

    urlsafe_query = query_to_base64(query_params)

    user_saved_queries = SavedSearch.objects.filter(
        Q(user=request.user) | Q(shared__exact=True)
    )

    # Search notice message
    search_message = ""
    is_sqlite = settings.DATABASES["default"]["ENGINE"].endswith("sqlite")
    user_is_searching = query_params.get("search_string")
    q = request.GET.get("q", "")

    if user_is_searching and is_sqlite:
        search_message = _(
            "<p><strong>Note:</strong> Your keyword search is case sensitive "
            "because of your database. This means the search will <strong>not</strong> "
            "be accurate. By switching to a different database system you will gain "
            "better searching! For more information, read the "
            '<a href="http://docs.djangoproject.com/en/dev/ref/databases/#sqlite-string-matching">'
            "Django Documentation on string matching in SQLite</a>."
        )

    kbitem_choices = []
    kbitems = []

    if helpdesk_settings.HELPDESK_KB_ENABLED:
        kbitem_choices = [(item.pk, str(item)) for item in KBItem.objects.all()]
        kbitems = KBItem.objects.all()

    ctx = {
        "query": q,
        "query_params": query_params,
        "default_tickets_per_page": request.user.usersettings_helpdesk.tickets_per_page,
        "assignable_users": get_assignable_users(
            helpdesk_settings.HELPDESK_STAFF_ONLY_TICKET_OWNERS
        ),
        "kb_items": kbitems,
        "kbitem_choices": kbitem_choices,
        "queue_choices": huser.get_queues(),
        "status_choices": Ticket.STATUS_CHOICES,
        "priority_choices": Ticket.PRIORITY_CHOICES,
        "urlsafe_query": urlsafe_query,
        "user_saved_queries": user_saved_queries,
        "from_saved_query": saved_query is not None,
        "saved_query": saved_query,
        "search_message": search_message,
        "helpdesk_settings": helpdesk_settings,
    }

    return render(request, "helpdesk/ticket_list.html", ctx)


class QueryLoadError(Exception):
    pass


def load_saved_query(request, query_params=None):
    saved_query = None

    if request.GET.get("saved_query", None):
        try:
            saved_query = SavedSearch.objects.get(
                Q(pk=request.GET.get("saved_query"))
                & (Q(shared=True) | Q(user=request.user))
            )
        except (SavedSearch.DoesNotExist, ValueError):
            raise QueryLoadError()

        try:
            # we get a string like: b'stuff'
            # so leave of the first two chars (b') and last (')
            if saved_query.query.startswith("b'"):
                b64query = saved_query.query[2:-1]
            else:
                b64query = saved_query.query
            query_params = query_from_base64(b64query)
        except json.JSONDecodeError:
            raise QueryLoadError()
    return saved_query, query_params


@helpdesk_staff_member_required
@api_view(["GET"])
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
@api_view(["GET"])
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

    return render(
        request,
        "helpdesk/edit_ticket.html",
        {"form": form, "ticket": ticket, "errors": form.errors},
    )


edit_ticket = staff_member_required(edit_ticket)


class CreateTicketView(
    MustBeStaffMixin, abstract_views.AbstractCreateTicketMixin, FormView
):
    template_name = "helpdesk/create_ticket.html"
    form_class = TicketForm

    def get_initial(self):
        initial_data = super().get_initial()
        return initial_data

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["queue_choices"] = get_user_queues(self.request.user)
        return kwargs

    def form_valid(self, form):
        self.ticket = form.save(
            user=self.request.user if self.request.user.is_authenticated else None
        )
        return super().form_valid(form)

    def get_success_url(self):
        request = self.request
        if HelpdeskUser(request.user).can_access_queue(self.ticket.queue):
            return self.ticket.get_absolute_url()
        else:
            return reverse("helpdesk:dashboard")


class UpdateTicketView(
    MustBeStaffMixin, abstract_views.AbstractCreateTicketMixin, UpdateView
):
    template_name = "helpdesk/ticket.html"
    form_class = TicketForm

    def get_initial(self):
        initial_data = super().get_initial()
        return initial_data

    def get_context_data(self, **kwargs):
        """Insert view context that would be lost after a POST."""
        extra = get_form_extra_kwargs(self.request.user)
        kwargs.update(extra)
        # Copy all data submitted that is not in the forms defined fields
        form = kwargs.get("form")
        if form is not None and hasattr(form, "data") and form.data:
            form_fields = form.base_fields
            all_fields = form.data
            self.extra_context = {
                "xform": {
                    k: v
                    for k, v in all_fields.items()
                    if k != "csrfmiddlewaretoken" and k not in form_fields
                }
            }
        else:
            self.extra_context = {"xform": {}}
        context = super().get_context_data(**kwargs)
        ticket = self.get_object()
        context["customfields_form"] = EditTicketCustomFieldForm(
            self.request.POST or None, instance=ticket
        )
        context["followups"] = get_followups_for_ticket(ticket)
        context["ticket_attachments"] = get_attachments_for_ticket(ticket)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # The ModelFormMixin adds "instance" which is then a problem in the
        kwargs["queue_choices"] = get_user_queues(self.request.user)
        kwargs["body_reqd"] = False
        return kwargs

    def get_object(self, queryset=None):
        ticket_id = self.kwargs["ticket_id"]
        return Ticket.objects.get(id=ticket_id)

    def form_valid(self, form):
        ticket_id = self.kwargs["ticket_id"]
        try:
            self.ticket = get_ticket_from_request_with_authorisation(
                self.request, ticket_id, False
            )
        except PermissionDenied:
            return redirect_to_login(self.request.path, "helpdesk:login")
        # Avoid calling super as it will call the save() method on the form
        save_ticket_update(form, self.ticket, self.request.user)
        return return_to_ticket(self.request.user, self.ticket)


@helpdesk_staff_member_required
def raw_details(request, type_):
    # TODO: This currently only supports spewing out 'PreSetReply' objects,
    # in the future it needs to be expanded to include other items. All it
    # does is return a plain-text representation of an object.

    if type_ not in ("preset",):
        raise Http404

    if type_ == "preset" and request.GET.get("id", False):
        try:
            preset = PreSetReply.objects.get(id=request.GET.get("id"))
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
        followup_title = _("Ticket taken off hold")
    else:
        ticket.on_hold = True
        followup_title = _("Ticket placed on hold")

    ticket.save()

    followup = FollowUp.objects.create(
        ticket=ticket,
        title=followup_title,
        date=now(),
        public=True,
        user=request.user,
    )

    TicketChange.objects.create(
        followup=followup,
        field=_("On Hold"),
        old_value=str(not ticket.on_hold),
        new_value=str(ticket.on_hold),
    )

    return HttpResponseRedirect(ticket.get_absolute_url())


hold_ticket = staff_member_required(hold_ticket)


@helpdesk_staff_member_required
@requires_csrf_token
def unhold_ticket(request, ticket_id):
    return hold_ticket(request, ticket_id, unhold=True)


unhold_ticket = staff_member_required(unhold_ticket)


@helpdesk_staff_member_required
def rss_list(request):
    return render(request, "helpdesk/rss_list.html", {"queues": Queue.objects.all()})


rss_list = staff_member_required(rss_list)


@helpdesk_staff_member_required
def report_index(request):
    number_tickets = Ticket.objects.all().count()
    saved_query = request.GET.get("saved_query", None)

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
            "queue": queue.id,
            "name": queue.title,
            "open": queue.ticket_set.filter(status__in=[1, 2]).count(),
            "resolved": queue.ticket_set.filter(status=3).count(),
            "closed": queue.ticket_set.filter(status=4).count(),
            "time_spent": format_time_spent(queue.time_spent),
            "dedicated_time": format_time_spent(queue.dedicated_time),
        }
        dash_tickets.append(dash_ticket)

    return render(
        request,
        "helpdesk/report_index.html",
        {
            "number_tickets": number_tickets,
            "saved_query": saved_query,
            "basic_ticket_stats": basic_ticket_stats,
            "dash_tickets": dash_tickets,
        },
    )


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
        "daysuntilticketclosedbymonth",
    ):
        return None, None, HttpResponseRedirect(reverse("helpdesk:report_index"))

    report_queryset = (
        Ticket.objects.all()
        .select_related()
        .filter(queue__in=HelpdeskUser(request.user).get_queues())
    )

    try:
        saved_query, query_params = load_saved_query(request)
    except QueryLoadError:
        return None, HttpResponseRedirect(reverse("helpdesk:report_index"))
    return report_queryset, query_params, saved_query, None


def get_report_table_and_totals(header1, summarytable, possible_options):
    table = []
    totals = {}
    for item in header1:
        data = []
        for hdr in possible_options:
            if hdr not in totals:
                totals[hdr] = summarytable[item, hdr]
            else:
                totals[hdr] += summarytable[item, hdr]
            data.append(summarytable[item, hdr])
        table.append([item] + data)
    return table, totals


def update_summary_tables(report_queryset, report, summarytable, summarytable2):
    metric3 = False
    for ticket in report_queryset:
        if report == "userpriority":
            metric1 = f"{ticket.get_assigned_to}"
            metric2 = f"{ticket.get_priority_display()}"

        elif report == "userqueue":
            metric1 = f"{ticket.get_assigned_to}"
            metric2 = f"{ticket.queue.title}"

        elif report == "userstatus":
            metric1 = f"{ticket.get_assigned_to}"
            metric2 = f"{ticket.get_status_display()}"

        elif report == "usermonth":
            metric1 = f"{ticket.get_assigned_to}"
            metric2 = f"{ticket.created.year}-{ticket.created.month}"

        elif report == "queuepriority":
            metric1 = f"{ticket.queue.title}"
            metric2 = f"{ticket.get_priority_display()}"

        elif report == "queuestatus":
            metric1 = f"{ticket.queue.title}"
            metric2 = f"{ticket.get_status_display()}"

        elif report == "queuemonth":
            metric1 = f"{ticket.queue.title}"
            metric2 = f"{ticket.created.year}-{ticket.created.month}"

        elif report == "daysuntilticketclosedbymonth":
            metric1 = f"{ticket.queue.title}"
            metric2 = f"{ticket.created.year}-{ticket.created.month}"
            metric3 = ticket.modified - ticket.created
            metric3 = metric3.days

        else:
            raise ValueError(f'report "{report}" is unrecognized.')

        summarytable[metric1, metric2] += 1
        if metric3 and report == "daysuntilticketclosedbymonth":
            summarytable2[metric1, metric2] += metric3


@helpdesk_staff_member_required
def run_report(request, report):
    report_queryset, query_params, saved_query, redirect = (
        get_report_queryset_or_redirect(request, report)
    )
    if redirect:
        return redirect
    if request.GET.get("saved_query", None):
        Query(report_queryset, query_to_base64(query_params))

    summarytable = defaultdict(int)
    # a second table for more complex queries
    summarytable2 = defaultdict(int)

    first_ticket = Ticket.objects.all().order_by("created")[0]
    first_month = first_ticket.created.month
    first_year = first_ticket.created.year

    last_ticket = Ticket.objects.all().order_by("-created")[0]
    last_month = last_ticket.created.month
    last_year = last_ticket.created.year

    periods = []
    year, month = first_year, first_month
    working = True
    periods.append(f"{year}-{month}")

    while working:
        month += 1
        if month > 12:
            year += 1
            month = 1
        if (year > last_year) or (month > last_month and year >= last_year):
            working = False
        periods.append(f"{year}-{month}")

    if report == "userpriority":
        title = _("User by Priority")
        col1heading = _("User")
        possible_options = [t[1].title() for t in Ticket.PRIORITY_CHOICES]
        charttype = "bar"

    elif report == "userqueue":
        title = _("User by Queue")
        col1heading = _("User")
        queue_options = HelpdeskUser(request.user).get_queues()
        possible_options = [q.title for q in queue_options]
        charttype = "bar"

    elif report == "userstatus":
        title = _("User by Status")
        col1heading = _("User")
        possible_options = [s[1].title() for s in Ticket.STATUS_CHOICES]
        charttype = "bar"

    elif report == "usermonth":
        title = _("User by Month")
        col1heading = _("User")
        possible_options = periods
        charttype = "date"

    elif report == "queuepriority":
        title = _("Queue by Priority")
        col1heading = _("Queue")
        possible_options = [t[1].title() for t in Ticket.PRIORITY_CHOICES]
        charttype = "bar"

    elif report == "queuestatus":
        title = _("Queue by Status")
        col1heading = _("Queue")
        possible_options = [s[1].title() for s in Ticket.STATUS_CHOICES]
        charttype = "bar"

    elif report == "queuemonth":
        title = _("Queue by Month")
        col1heading = _("Queue")
        possible_options = periods
        charttype = "date"

    elif report == "daysuntilticketclosedbymonth":
        title = _("Days until ticket closed by Month")
        col1heading = _("Queue")
        possible_options = periods
        charttype = "date"
    update_summary_tables(report_queryset, report, summarytable, summarytable2)
    if report == "daysuntilticketclosedbymonth":
        for key in summarytable2:
            summarytable[key] = round(summarytable2[key] / summarytable[key], 2)

    header1 = sorted({i for i, _ in summarytable})

    column_headings = [col1heading] + possible_options

    # Prepare a dict to store totals for each possible option
    table, totals = get_report_table_and_totals(header1, summarytable, possible_options)
    # Pivot the data so that 'header1' fields are always first column
    # in the row, and 'possible_options' are always the 2nd - nth columns.

    # Zip data and headers together in one list for Morris.js charts
    # will get a list like [(Header1, Data1), (Header2, Data2)...]
    morrisjs_data = []
    for seriesnum, label in enumerate(column_headings[1:], start=1):
        datadict = {"x": label}
        for n in range(len(table)):
            datadict[n] = table[n][seriesnum]
        morrisjs_data.append(datadict)

    series_names = []
    for series in table:
        series_names.append(series[0])

    # Add total row to table
    total_data = ["Total"]
    for hdr in possible_options:
        val = totals[hdr]
        if report == "daysuntilticketclosedbymonth":
            val = round(val, 2)
        total_data.append(str(val))

    return render(
        request,
        "helpdesk/report_output.html",
        {
            "title": title,
            "charttype": charttype,
            "data": table,
            "total_data": total_data,
            "headings": column_headings,
            "series_names": series_names,
            "morrisjs_data": morrisjs_data,
            "from_saved_query": saved_query is not None,
            "saved_query": saved_query,
        },
    )


run_report = staff_member_required(run_report)


@helpdesk_staff_member_required
def saved_searches_list(request):
    user = request.user
    saved_queries = SavedSearch.objects.filter(Q(user=user) | Q(shared=True)).distinct()

    return render(
        request,
        "helpdesk/saved_searches_list.html",
        {
            "saved_queries": saved_queries,
        },
    )


saved_searches_list = staff_member_required(saved_searches_list)


@helpdesk_staff_member_required
def save_query(request):
    title = request.POST.get("title", None)
    shared = request.POST.get("shared", False)
    if shared == "on":  # django only translates '1', 'true', 't' into True
        shared = True
    query_encoded = request.POST.get("query_encoded", None)

    if not title or not query_encoded:
        return HttpResponseRedirect(reverse("helpdesk:list"))

    query = SavedSearch(
        title=title, shared=shared, query=query_encoded, user=request.user
    )
    query.save()

    return HttpResponseRedirect(
        "{}?saved_query={}".format(reverse("helpdesk:list"), query.id)
    )


save_query = staff_member_required(save_query)


@helpdesk_staff_member_required
def delete_saved_query(request, pk):
    query = get_object_or_404(SavedSearch, id=pk, user=request.user)

    if request.method == "POST":
        query.delete()
        return HttpResponseRedirect(reverse("helpdesk:list"))
    else:
        return render(
            request, "helpdesk/confirm_delete_saved_query.html", {"query": query}
        )


delete_saved_query = staff_member_required(delete_saved_query)


class EditUserSettingsView(MustBeStaffMixin, UpdateView):
    template_name = "helpdesk/user_settings.html"
    form_class = UserSettingsForm
    model = UserSettings
    success_url = reverse_lazy("helpdesk:dashboard")

    def get_object(self, queryset=None):
        return UserSettings.objects.get_or_create(user=self.request.user)[0]


@helpdesk_superuser_required
def email_ignore(request):
    return render(
        request,
        "helpdesk/email_ignore_list.html",
        {
            "ignore_list": IgnoreEmail.objects.all(),
        },
    )


email_ignore = superuser_required(email_ignore)


@helpdesk_superuser_required
def email_ignore_add(request):
    if request.method == "POST":
        form = EmailIgnoreForm(request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse("helpdesk:email_ignore"))
    else:
        form = EmailIgnoreForm(request.GET)

    return render(request, "helpdesk/email_ignore_add.html", {"form": form})


email_ignore_add = superuser_required(email_ignore_add)


@helpdesk_superuser_required
def email_ignore_del(request, pk):
    ignore = get_object_or_404(IgnoreEmail, id=pk)
    if request.method == "POST":
        ignore.delete()
        return HttpResponseRedirect(reverse("helpdesk:email_ignore"))
    else:
        return render(request, "helpdesk/email_ignore_del.html", {"ignore": ignore})


email_ignore_del = superuser_required(email_ignore_del)


@helpdesk_staff_member_required
def ticket_cc(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    copies_to = ticket.ticketcc_set.all()
    return render(
        request,
        "helpdesk/ticket_cc_list.html",
        {
            "copies_to": copies_to,
            "ticket": ticket,
        },
    )


ticket_cc = staff_member_required(ticket_cc)


@helpdesk_staff_member_required
def ticket_cc_add(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    form = None
    if request.method == "POST":
        form = TicketCCForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data.get("user")
            email = form.cleaned_data.get("email")
            if user and ticket.ticketcc_set.filter(user=user).exists():
                form.add_error("user", _("Impossible to add twice the same user"))
            elif email and ticket.ticketcc_set.filter(email=email).exists():
                form.add_error(
                    "email", _("Impossible to add twice the same email address")
                )
            else:
                ticketcc = form.save(commit=False)
                ticketcc.ticket = ticket
                ticketcc.save()
                return HttpResponseRedirect(
                    reverse("helpdesk:ticket_cc", kwargs={"ticket_id": ticket.id})
                )

    return render(
        request,
        "helpdesk/ticket_cc_add.html",
        {
            "ticket": ticket,
            "form": form,
            "form_email": TicketCCEmailForm(),
            "form_user": TicketCCUserForm(),
        },
    )


ticket_cc_add = staff_member_required(ticket_cc_add)


@helpdesk_staff_member_required
def ticket_cc_del(request, ticket_id, cc_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)
    cc = get_object_or_404(TicketCC, ticket__id=ticket_id, id=cc_id)

    if request.method == "POST":
        cc.delete()
        return HttpResponseRedirect(
            reverse("helpdesk:ticket_cc", kwargs={"ticket_id": cc.ticket.id})
        )

    return render(request, "helpdesk/ticket_cc_del.html", {"ticket": ticket, "cc": cc})


ticket_cc_del = staff_member_required(ticket_cc_del)


@helpdesk_staff_member_required
def ticket_dependency_add(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)
    if request.method == "POST":
        form = TicketDependencyForm(ticket, request.POST)
        if form.is_valid():
            ticketdependency = form.save(commit=False)
            ticketdependency.ticket = ticket
            if ticketdependency.ticket != ticketdependency.depends_on:
                ticketdependency.save()
            return redirect(ticket.get_absolute_url())
    else:
        form = TicketDependencyForm(ticket)
    return render(
        request,
        "helpdesk/ticket_dependency_add.html",
        {
            "ticket": ticket,
            "form": form,
        },
    )


ticket_dependency_add = staff_member_required(ticket_dependency_add)


@helpdesk_staff_member_required
def ticket_dependency_del(request, ticket_id, dependency_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)
    dependency = get_object_or_404(
        TicketDependency, ticket__id=ticket_id, id=dependency_id
    )
    if request.method == "POST":
        dependency.delete()
        return HttpResponseRedirect(reverse("helpdesk:view", args=[ticket_id]))
    return render(
        request, "helpdesk/ticket_dependency_del.html", {"dependency": dependency}
    )


ticket_dependency_del = staff_member_required(ticket_dependency_del)


@helpdesk_staff_member_required
def ticket_resolves_add(request, ticket_id):
    depends_on = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, depends_on)
    if request.method == "POST":
        form = TicketResolvesForm(depends_on, request.POST)
        if form.is_valid():
            ticketdependency = form.save(commit=False)
            ticketdependency.depends_on = depends_on
            if ticketdependency.ticket != ticketdependency.depends_on:
                ticketdependency.save()
            return redirect(depends_on.get_absolute_url())
    else:
        form = TicketResolvesForm(depends_on)
    return render(
        request,
        "helpdesk/ticket_resolves_add.html",
        {
            "depends_on": depends_on,
            "form": form,
        },
    )


ticket_resolves_add = staff_member_required(ticket_resolves_add)


@helpdesk_staff_member_required
def ticket_resolves_del(request, ticket_id, dependency_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)
    dependency = get_object_or_404(
        TicketDependency, ticket__id=ticket_id, id=dependency_id
    )
    depends_on_id = dependency.depends_on.id
    if request.method == "POST":
        dependency.delete()
        return HttpResponseRedirect(reverse("helpdesk:view", args=[depends_on_id]))
    return render(
        request, "helpdesk/ticket_dependency_del.html", {"dependency": dependency}
    )


ticket_resolves_del = staff_member_required(ticket_resolves_del)


@helpdesk_staff_member_required
def attachment_preview(request, ticket_id, attachment_id):
    """Render an attachment that holds HTML, with the markup neutralised.

    Attachments are otherwise linked straight into MEDIA_ROOT and served by the
    web server, which picks the content type from the file extension. That is why
    an inbound email's HTML body is stored as .txt: it makes the direct link
    inert. This view is the only place that turns those bytes back into a
    rendered document, so it is also the only place that has to be defended, and
    it is defended three times over. See helpdesk.sanitize for what each layer
    does and why sanitizing happens here rather than at upload time.

    Going through a view has a second benefit the raw media link never had: the
    queue and ticket permission checks below actually run.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    attachment = get_object_or_404(
        FollowUpAttachment, id=attachment_id, followup__ticket=ticket
    )
    if attachment.mime_type != "text/html":
        raise Http404("This attachment has no HTML rendering.")

    if not sanitizer_available():
        # Fail closed. Serving the raw bytes as text/html here would hand the
        # sender exactly the XSS this view exists to prevent.
        return HttpResponse(
            "HTML previews are unavailable because the nh3 package is not "
            "installed. Download the attachment to read its source instead.",
            content_type="text/plain; charset=utf-8",
            status=503,
        )

    attachment.file.open("rb")
    try:
        raw = attachment.file.read()
    finally:
        attachment.file.close()

    response = HttpResponse(
        sanitize_email_html(raw.decode("utf-8", errors="replace")),
        content_type="text/html; charset=utf-8",
    )
    response["Content-Security-Policy"] = preview_csp()
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "no-referrer"
    return response


@helpdesk_staff_member_required
def attachment_del(request, ticket_id, attachment_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket_perm_check(request, ticket)

    attachment = get_object_or_404(
        FollowUpAttachment, id=attachment_id, followup__ticket=ticket
    )
    if request.method == "POST":
        attachment.delete()
        return HttpResponseRedirect(reverse("helpdesk:view", args=[ticket_id]))
    return render(
        request,
        "helpdesk/ticket_attachment_del.html",
        {
            "attachment": attachment,
            "filename": attachment.filename,
        },
    )


def calc_average_nbr_days_until_ticket_resolved(Tickets):
    nbr_closed_tickets = len(Tickets)
    days_per_ticket = 0
    days_each_ticket = []

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
    today = timezone.now()

    date_30 = date_rel_to_today(today, 30)
    date_60 = date_rel_to_today(today, 60)
    date_30_str = date_30.strftime(CUSTOMFIELD_DATE_FORMAT)
    date_60_str = date_60.strftime(CUSTOMFIELD_DATE_FORMAT)

    # > 0 & <= 30
    ota_le_30 = all_open_tickets.filter(created__gte=date_30_str)
    N_ota_le_30 = len(ota_le_30)

    # >= 30 & <= 60
    ota_le_60_ge_30 = all_open_tickets.filter(
        created__gte=date_60_str, created__lte=date_30_str
    )
    N_ota_le_60_ge_30 = len(ota_le_60_ge_30)

    # >= 60
    ota_ge_60 = all_open_tickets.filter(created__lte=date_60_str)
    N_ota_ge_60 = len(ota_ge_60)

    # (O)pen (T)icket (S)tats
    ots = []
    # label, number entries, color, sort_string
    ots.append(
        [
            "Tickets < 30 days",
            N_ota_le_30,
            "success",
            sort_string(date_30_str, ""),
        ]
    )
    ots.append(
        [
            "Tickets 30 - 60 days",
            N_ota_le_60_ge_30,
            "success" if N_ota_le_60_ge_30 == 0 else "warning",
            sort_string(date_60_str, date_30_str),
        ]
    )
    ots.append(
        [
            "Tickets > 60 days",
            N_ota_ge_60,
            "success" if N_ota_ge_60 == 0 else "danger",
            sort_string("", date_60_str),
        ]
    )

    # all closed tickets - independent of user.
    all_closed_tickets = Tickets.filter(status=Ticket.CLOSED_STATUS)
    average_nbr_days_until_ticket_closed = calc_average_nbr_days_until_ticket_resolved(
        all_closed_tickets
    )
    # all closed tickets that were opened in the last 60 days.
    all_closed_last_60_days = all_closed_tickets.filter(created__gte=date_60_str)
    average_nbr_days_until_ticket_closed_last_60_days = (
        calc_average_nbr_days_until_ticket_resolved(all_closed_last_60_days)
    )

    # put together basic stats
    basic_ticket_stats = {
        "average_nbr_days_until_ticket_closed": average_nbr_days_until_ticket_closed,
        "average_nbr_days_until_ticket_closed_last_60_days": average_nbr_days_until_ticket_closed_last_60_days,
        "open_ticket_stats": ots,
    }

    return basic_ticket_stats


def get_color_for_nbr_days(nbr_days):
    if nbr_days < 5:
        color_string = "green"
    elif nbr_days < 10:
        color_string = "orange"
    else:  # more than 10 days
        color_string = "red"

    return color_string


def days_since_created(today, ticket):
    return (today - ticket.created).days


def date_rel_to_today(today, offset):
    return today - timedelta(days=offset)


def sort_string(begin, end):
    return f"sort=created&date_from={begin}&date_to={end}&status={Ticket.OPEN_STATUS}&status={Ticket.REOPENED_STATUS}&status={Ticket.RESOLVED_STATUS}"


@helpdesk_staff_member_required
def checklist_templates(request, checklist_template_id=None):
    checklist_template = None
    if checklist_template_id:
        checklist_template = get_object_or_404(
            ChecklistTemplate, id=checklist_template_id
        )
    form = ChecklistTemplateForm(request.POST or None, instance=checklist_template)
    if form.is_valid():
        form.save()
        return redirect("helpdesk:checklist_templates")
    return render(
        request,
        "helpdesk/checklist_templates.html",
        {
            "checklists": ChecklistTemplate.objects.all(),
            "checklist_template": checklist_template,
            "form": form,
        },
    )


@helpdesk_staff_member_required
def delete_checklist_template(request, checklist_template_id):
    checklist_template = get_object_or_404(ChecklistTemplate, id=checklist_template_id)
    if request.method == "POST":
        checklist_template.delete()
        return redirect("helpdesk:checklist_templates")
    return render(
        request,
        "helpdesk/checklist_template_confirm_delete.html",
        {
            "checklist_template": checklist_template,
        },
    )


@helpdesk_staff_member_required
def kanban_board(request):
    huser = HelpdeskUser(request.user)
    base_qs = Ticket.objects.select_related("queue", "assigned_to").only(
        "id",
        "title",
        "priority",
        "status",
        "due_date",
        "modified",
        "queue__title",
        "assigned_to__username",
    )

    queue_ids = list(huser.get_queues().values_list("pk", flat=True))
    tickets = base_qs.filter(queue_id__in=queue_ids)

    now = timezone.now()
    default_due_weeks = helpdesk_settings.HELPDESK_KANBAN_DEFAULT_DUE_WEEKS or 2
    exclude_overdue = request.GET.get("exclude_overdue") == "1"
    raw_weeks = request.GET.get("due_weeks", "").strip()
    try:
        parsed = int(raw_weeks) if raw_weeks else None
        if parsed is None:
            due_weeks = default_due_weeks  # no param → use default
        elif parsed <= 0:
            due_weeks = None  # explicit 0 → show all
        else:
            due_weeks = parsed
    except ValueError:
        due_weeks = default_due_weeks

    if due_weeks:
        cutoff = now + timedelta(weeks=due_weeks)
        upcoming_q = Q(due_date__isnull=False, due_date__gte=now, due_date__lte=cutoff)
        overdue_q = Q(
            due_date__isnull=False, due_date__lt=now, status__in=Ticket.OPEN_STATUSES
        )
        tickets = tickets.filter(
            upcoming_q if exclude_overdue else upcoming_q | overdue_q
        )

    closed_weeks = (
        helpdesk_settings.HELPDESK_KANBAN_DEFAULT_RENDER_CLOSED_TICKETS_WEEKS or None
    )
    if closed_weeks:
        closed_cutoff = now - timedelta(weeks=closed_weeks)
        closed_statuses = [Ticket.CLOSED_STATUS, Ticket.DUPLICATE_STATUS]
        tickets = tickets.exclude(
            status__in=closed_statuses, modified__lt=closed_cutoff
        )

    tickets = tickets.order_by(F("due_date").asc(nulls_last=True), "-modified")

    bucket = {}
    for t in tickets:
        bucket.setdefault(t.status, []).append(t)

    columns = [
        {
            "status": status_value,
            "label": status_label,
            "tickets": bucket.get(status_value, []),
        }
        for status_value, status_label in Ticket.STATUS_CHOICES
    ]

    return render(
        request,
        "helpdesk/kanban.html",
        {
            "columns": columns,
            "due_weeks": due_weeks,
            "default_due_weeks": default_due_weeks,
            "exclude_overdue": exclude_overdue,
            "now": now,
        },
    )


@helpdesk_staff_member_required
def kanban_update_ticket(request, ticket_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    ticket = get_object_or_404(Ticket, id=ticket_id)
    huser = HelpdeskUser(request.user)
    if ticket.queue not in huser.get_queues():
        return JsonResponse({"error": "Permission denied"}, status=403)
    try:
        data = json.loads(request.body)
        new_status = int(data["status"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid data"}, status=400)
    valid_statuses = [s for s, _ in Ticket.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return JsonResponse({"error": "Invalid status"}, status=400)
    ticket.status = new_status
    ticket.save(update_fields=["status", "modified"])
    return JsonResponse({"status": "ok", "new_status": new_status})
