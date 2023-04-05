"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/staff.py - The bulk of the application - provides most business logic and
                 renders all staff-facing views.
"""
from copy import deepcopy
import json
import pandas as pd
import dateutil
import pytz

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse, reverse_lazy
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Prefetch, F
from django.http import HttpResponseRedirect, Http404, HttpResponse, JsonResponse, HttpRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import ugettext as _
from django.utils.html import escape
from django.utils import timezone
from django.views.generic.edit import FormView, UpdateView

from helpdesk.forms import CUSTOMFIELD_DATE_FORMAT, CUSTOMFIELD_DATETIME_FORMAT
from helpdesk.query import (
    get_query_class,
    query_to_base64,
    query_from_base64,
    get_extra_data_columns,
)

from helpdesk.serializers import DatatablesTicketSerializer, ReportTicketSerializer

from helpdesk.user import HelpdeskUser

from helpdesk.decorators import (
    helpdesk_staff_member_required,
    helpdesk_superuser_required,
    is_helpdesk_staff,
    list_of_helpdesk_staff,
    superuser_required,
)
from helpdesk.forms import (
    TicketForm, UserSettingsForm, EmailIgnoreForm, EditTicketForm, TicketCCForm,
    TicketCCEmailForm, TicketCCUserForm, EditFollowUpForm, TicketDependencyForm, MultipleTicketSelectForm
)
from helpdesk.lib import (
    safe_template_context,
    process_attachments,
    queue_template_context,
)
from helpdesk.models import (
    Ticket, Queue, FollowUp, TicketChange, PreSetReply, FollowUpAttachment, SavedSearch,
    IgnoreEmail, TicketCC, TicketDependency, UserSettings, KBItem, CustomField, is_unlisted,
    FormType
)

from helpdesk import settings as helpdesk_settings
import helpdesk.views.abstract_views as abstract_views
from helpdesk.views.permissions import MustBeStaffMixin
from ..lib import format_time_spent

from rest_framework import status
from rest_framework.decorators import api_view

from datetime import timedelta

from ..templated_email import send_templated_mail

from seed.models import PropertyView, Property, TaxLotView, TaxLot
from urllib.parse import urlparse, urlunparse
from django.http import QueryDict
User = get_user_model()
Query = get_query_class()

staff_member_required = user_passes_test(
    lambda u: u.is_authenticated and u.is_active and is_helpdesk_staff(u))


def set_user_timezone(request):
    if 'helpdesk_timezone' not in request.session:
        tz = request.GET.get('timezone')
        request.session["helpdesk_timezone"] = tz
        timezone.activate(tz)
        response_data = {'status': True, 'message': 'user timezone set successfully to %s.' % tz}
    else:
        response_data = {'status': False, 'message': 'user timezone has already been set'}
    return JsonResponse(response_data, status=status.HTTP_200_OK)


@helpdesk_staff_member_required
def set_default_org(request, user_id, org_id):
    """
    Change the default org of the user based on their dropdown menu selection
    Reload them back to the same page
    """
    from seed.landing.models import SEEDUser as User
    from seed.lib.superperms.orgs.models import Organization
    user = User.objects.get(pk=user_id)
    user.default_organization_id = org_id
    user.save()

    # todo The query is changed, which is good, but the path didn't, and that can be wrong. grrr
    # complicated way of replacing the org query with the new org's name
    # https://stackoverflow.com/questions/5755150/altering-one-query-parameter-in-a-url-django
    (scheme, netloc, path, params, query, fragment) = urlparse(request.META['HTTP_REFERER'])
    query_dict = QueryDict(query).copy()
    query_dict['org'] = Organization.objects.get(id=org_id).name
    query = query_dict.urlencode()
    url = urlunparse((scheme, netloc, path, params, query, fragment))
    return redirect(url)


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
    all_tickets_reported_by_current_user_page = request.GET.get(_('atrbcu_page'), 1)
    unassigned_tickets_page = request.GET.get(_('uat_page'), 1)

    huser = HelpdeskUser(request.user)
    user_queues = huser.get_queues()                # Queues in user's default org (or all if superuser)
    active_tickets = Ticket.objects.select_related('queue').exclude(
        status__in=[Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS],
    )

    # Get only active tickets
    active_tickets = active_tickets.filter(
        queue__in=user_queues)

    # open & reopened tickets, assigned to current user
    tickets = active_tickets.filter(
        assigned_to=request.user,
    )

    # closed & resolved tickets, assigned to current user
    tickets_closed_resolved = Ticket.objects.select_related('queue').filter(
        assigned_to=request.user,
        status__in=[Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS],
        queue__in=user_queues,
    )

    unassigned_tickets = active_tickets.filter(
        assigned_to__isnull=True,
        kbitem__isnull=True,
        queue__in=user_queues,
    )

    kbitems = huser.get_assigned_kb_items()

    # all tickets, reported by current user, in their default org
    all_tickets_reported_by_current_user = ''
    email_current_user = request.user.email
    if email_current_user:
        all_tickets_reported_by_current_user = Ticket.objects.select_related('queue').filter(
            submitter_email=email_current_user,
            queue__in=user_queues
        ).order_by('status', '-id')

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

    # get unassigned tickets page
    paginator = Paginator(
        unassigned_tickets, tickets_per_page)
    try:
        unassigned_tickets = paginator.page(
            unassigned_tickets_page)
    except PageNotAnInteger:
        unassigned_tickets = paginator.page(1)
    except EmptyPage:
        unassigned_tickets = paginator.page(
            paginator.num_pages)

    return render(request, 'helpdesk/dashboard.html', {
        'user_tickets': tickets,
        'user_tickets_closed_resolved': tickets_closed_resolved,
        'unassigned_tickets': unassigned_tickets,
        'kbitems': kbitems,
        'all_tickets_reported_by_current_user': all_tickets_reported_by_current_user,
        'basic_ticket_stats': basic_ticket_stats,
        'debug': settings.DEBUG,
    })


dashboard = staff_member_required(dashboard)


def ticket_perm_check(request, ticket):
    huser = HelpdeskUser(request.user, request)
    if not huser.check_default_org(ticket.ticket_form.organization):
        return HttpResponseRedirect(reverse('helpdesk:home'))
    else:
        if not huser.can_access_queue(ticket.queue):
            raise PermissionDenied()
        if not huser.can_access_ticket(ticket):
            raise PermissionDenied()


@helpdesk_staff_member_required
def delete_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    perm = ticket_perm_check(request, ticket)
    if perm is not None:
        return perm

    if request.method == 'GET':
        return render(request, 'helpdesk/delete_ticket.html', {
            'ticket': ticket,
            'next': request.GET.get('next', 'home'),
            'debug': settings.DEBUG,
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
    perm = ticket_perm_check(request, ticket)
    if perm is not None:
        return perm

    if request.method == 'GET':
        form = EditFollowUpForm(initial={
            'title': escape(followup.title),
            'ticket': followup.ticket,
            'comment': escape(followup.comment),
            'public': followup.public,
            'new_status': followup.new_status,
            'time_spent': format_time_spent(followup.time_spent),
        })

        ticketcc_string, show_subscribe = \
            return_ticketccstring_and_show_subscribe(request.user, ticket)

        return render(request, 'helpdesk/followup_edit.html', {
            'followup': followup,
            'ticket': ticket,
            'form': form,
            'ticketcc_string': ticketcc_string,
            'debug': settings.DEBUG,
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
    perm = ticket_perm_check(request, ticket)
    if perm is not None:
        return perm

    if 'take' in request.GET:
        # Allow the user to assign the ticket to themselves whilst viewing it.

        # Trick the update_ticket() view into thinking it's being called with
        # a valid POST.
        request.POST = {
            'owner': request.user.id,
            'public': 0,
            'title': ticket.title,
            'comment': ''
        }
        return update_ticket(request, ticket_id)

    if 'subscribe' in request.GET:
        # Allow the user to subscribe him/herself to the ticket whilst viewing it.
        ticket_cc, show_subscribe = \
            return_ticketccstring_and_show_subscribe(request.user, ticket)
        if show_subscribe:
            subscribe_staff_member_to_ticket(ticket, request.user)
            return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket.id]))

    if 'close' in request.GET and ticket.status == Ticket.RESOLVED_STATUS:
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

    org = ticket.ticket_form.organization_id
    users = list_of_helpdesk_staff(org)
    # TODO add back HELPDESK_STAFF_ONLY_TICKET_OWNERS setting
    """if helpdesk_settings.HELPDESK_STAFF_ONLY_TICKET_OWNERS:
        staff_ids = [u.id for u in users if is_helpdesk_staff(u, org=org)]  # todo
        users = users.filter(id__in=staff_ids)"""
    users = users.order_by(User.USERNAME_FIELD)

    queues = Queue.objects.filter(organization=org)
    queue_choices = _get_queue_choices(queues)
    # TODO: shouldn't this template get a form to begin with?
    form = TicketForm(initial={'due_date': ticket.due_date},
                      queue_choices=queue_choices,
                      form_id=ticket.ticket_form.pk)

    ticketcc_string, show_subscribe = \
        return_ticketccstring_and_show_subscribe(request.user, ticket)

    submitter_userprofile = ticket.get_submitter_userprofile()
    """if submitter_userprofile is not None:
        content_type = ContentType.objects.get_for_model(submitter_userprofile)
        submitter_userprofile_url = reverse(
            'admin:{app}_{model}_change'.format(app=content_type.app_label, model=content_type.model),
            kwargs={'object_id': submitter_userprofile.id}  # TODO problem
        )
    else:"""
    submitter_userprofile_url = None

    display_data = CustomField.objects.filter(ticket_form=ticket.ticket_form).only(
        'label', 'data_type',
        'field_name', 'columns',
    )
    extra_data = []
    for values, object in zip(display_data.values(), display_data):  # TODO check how many queries this runs
        if not is_unlisted(values['field_name']) and not values['data_type'] == 'attachment':
            if values['field_name'] in ticket.extra_data:
                values['value'] = ticket.extra_data[values['field_name']]
            else:
                values['value'] = getattr(ticket, values['field_name'], None)
            values['has_columns'] = True if object.columns.exists() else False
            extra_data.append(values)

    properties = list(
        PropertyView.objects.filter(property_id__in=ticket.beam_property.all().values_list('id', flat=True))
        .order_by('property_id', '-cycle__end').distinct('property_id').values('id', 'property_id', address=F('state__address_line_1')))
    taxlots = list(
        TaxLotView.objects.filter(taxlot_id__in=ticket.beam_taxlot.all().values_list('id', flat=True))
        .order_by('taxlot_id', '-cycle__end').distinct('taxlot_id').values('id', 'taxlot_id', address=F('state__address_line_1')))

    for p in properties:
        if p['address'] is None or p['address'] == '':
            p['address'] = '(No address found)'
    for t in taxlots:
        if t['address'] is None or t['address'] == '':
            t['address'] = '(No address found)'

    return render(request, 'helpdesk/ticket.html', {
        'ticket': ticket,
        'submitter_userprofile_url': submitter_userprofile_url,
        'form': form,
        'active_users': users,
        'priorities': Ticket.PRIORITY_CHOICES,
        'preset_replies': PreSetReply.objects.filter(
            Q(queues=ticket.queue) | Q(queues__isnull=True)),
        'ticketcc_string': ticketcc_string,
        'SHOW_SUBSCRIBE': show_subscribe,
        'extra_data': extra_data,
        'properties': properties,
        'taxlots': taxlots,
        'is_staff': is_helpdesk_staff(request.user),
        'debug': settings.DEBUG,
    })


def return_ticketccstring_and_show_subscribe(user, ticket):
    """used in view_ticket() and followup_edit()"""
    # create the ticketcc_string and check whether current user is already
    # subscribed
    username = user.get_username().upper()
    useremail = user.email.upper()
    strings_to_check = list()
    strings_to_check.append(username)
    strings_to_check.append(useremail)

    ticketcc_string = ''
    all_ticketcc = ticket.ticketcc_set.all()
    counter_all_ticketcc = len(all_ticketcc) - 1
    show_subscribe = True
    for i, ticketcc in enumerate(all_ticketcc):
        ticketcc_this_entry = str(ticketcc.display)
        ticketcc_string += ticketcc_this_entry
        if i < counter_all_ticketcc:
            ticketcc_string += ', '
        if strings_to_check.__contains__(ticketcc_this_entry.upper()):
            show_subscribe = False

    # check whether current user is a submitter or assigned to ticket
    assignedto_username = str(ticket.assigned_to).upper()
    strings_to_check = list()
    if ticket.submitter_email is not None:
        submitter_email = ticket.submitter_email.upper()
        strings_to_check.append(submitter_email)
    strings_to_check.append(assignedto_username)
    if strings_to_check.__contains__(username) or strings_to_check.__contains__(useremail):
        show_subscribe = False

    return ticketcc_string, show_subscribe


def subscribe_to_ticket_updates(ticket, user=None, email=None, can_view=True, can_update=False):
    if ticket is not None:
        queryset = TicketCC.objects.filter(ticket=ticket, user=user, email=email)

        # Don't create duplicate entries for subscribers
        if queryset.count() > 0:
            return None

        if user is None and len(email) < 5:
            raise ValidationError(
                _('When you add somebody on Cc, you must provide either a User or a valid email. Email: %s' % email)
            )

        ticketcc = TicketCC(
            ticket=ticket,
            user=user,
            email=email,
            can_view=can_view,
            can_update=can_update
        )
        ticketcc.save()
        return ticketcc


def subscribe_staff_member_to_ticket(ticket, user, email='', can_view=True, can_update=False):
    """used in view_ticket() and update_ticket()"""
    return subscribe_to_ticket_updates(ticket=ticket, user=user, email=email, can_view=can_view, can_update=can_update)


def update_ticket(request, ticket_id, public=False):
    ticket = None
    # So if the update isn't public, or the user isn't a staff member:
    # Locate the ticket through the submitter email and the secret key.
    if not (public or is_helpdesk_staff(request.user)):

        key = request.POST.get('key')
        email = request.POST.get('mail')

        if key and email:
            ticket = Ticket.objects.get(
                id=ticket_id,
                submitter_email__iexact=email,  # TODO: Other email fields should work for this too.  # todo todo
                secret_key__iexact=key
            )

        if not ticket:
            return HttpResponseRedirect(
                '%s?next=%s' % (reverse('helpdesk:login'), request.path)
            )

    if not ticket:
        ticket = get_object_or_404(Ticket, id=ticket_id)

    comment = request.POST.get('comment', '')
    new_status = int(request.POST.get('new_status', ticket.status))
    title = request.POST.get('title', '')
    public = request.POST.get('public', False)
    owner = int(request.POST.get('owner', -1))
    priority = int(request.POST.get('priority', ticket.priority))
    mins_spent = int(request.POST.get("time_spent", '0').strip() or '0')
    time_spent = timedelta(minutes=mins_spent)

    # NOTE: jQuery's default for dates is mm/dd/yy
    # very US-centric but for now that's the only format supported
    # until we clean up code to internationalize a little more
    due_date = request.POST.get('due_date', None)
    due_date = due_date if due_date else None

    utc = pytz.timezone('UTC')
    if due_date is not None:
        # https://stackoverflow.com/questions/26264897/time-zone-field-in-isoformat
        due_date = timezone.get_current_timezone().localize(dateutil.parser.parse(due_date))
        due_date = due_date.astimezone(utc)

    no_changes_excluding_time_spent = all([  # excludes spent time so we can re-use it to send emails
        not request.FILES,
        not comment,
        new_status == ticket.status,
        title == ticket.title,
        priority == int(ticket.priority),
        due_date == ticket.due_date,
        (owner == -1) or (not owner and not ticket.assigned_to) or
        (owner and User.objects.get(id=owner) == ticket.assigned_to),
    ])
    if no_changes_excluding_time_spent and mins_spent == 0:
        return return_to_ticket(request.user, request, helpdesk_settings, ticket)

    # We need to allow the 'ticket' and 'queue' contexts to be applied to the
    # comment.
    context = safe_template_context(ticket)

    from django.template import engines
    template_func = engines['django'].from_string
    # this prevents system from trying to render any template tags
    # broken into two stages to prevent changes from first replace being themselves
    # changed by the second replace due to conflicting syntax
    comment = comment.replace('{%', 'X-HELPDESK-COMMENT-VERBATIM').replace('%}', 'X-HELPDESK-COMMENT-ENDVERBATIM')
    comment = comment.replace(
        'X-HELPDESK-COMMENT-VERBATIM', '{% verbatim %}{%'
    ).replace(
        'X-HELPDESK-COMMENT-ENDVERBATIM', '%}{% endverbatim %}'
    )
    # render the neutralized template
    comment = template_func(comment).render(context)

    if owner == -1 and ticket.assigned_to:
        owner = ticket.assigned_to.id

    f = FollowUp(ticket=ticket, date=timezone.now(), comment=comment,
                 time_spent=time_spent)

    if is_helpdesk_staff(request.user, ticket.ticket_form.organization_id):
        f.user = request.user

    f.public = public

    old_status_str = ticket.get_status_display()
    old_status = ticket.status

    reassigned = False
    old_owner = ticket.assigned_to

    if owner != -1:
        if owner != 0 and ((ticket.assigned_to and owner != ticket.assigned_to.id) or not ticket.assigned_to):
            new_user = User.objects.get(id=owner)
            f.title = _('Assigned to %(name)s') % {
                'name': new_user.get_full_name() or new_user.get_username(),
            }
            ticket.assigned_to = new_user
            reassigned = True
        # user changed owner to 'unassign'
        elif owner == 0 and ticket.assigned_to is not None:
            f.title = _('Unassigned')
            ticket.assigned_to = None
        elif ticket.queue.reassign_when_closed and ticket.assigned_to and owner == ticket.assigned_to.id and (
                ticket.queue.default_owner and new_status != ticket.status and new_status == Ticket.CLOSED_STATUS):
            new_user = ticket.queue.default_owner
            f.title = _('Assigned to %(name)s') % {
                'name': new_user.get_full_name() or new_user.get_username(),
            }
            ticket.assigned_to = new_user
            reassigned = True
    elif ticket.queue.reassign_when_closed and (
            ticket.queue.default_owner and new_status != ticket.status and new_status == Ticket.CLOSED_STATUS):
        # if no owner already assigned in this update, set the default owner if the ticket is being closed
        new_user = ticket.queue.default_owner
        f.title = _('Assigned to %(name)s') % {
            'name': new_user.get_full_name() or new_user.get_username(),
        }
        ticket.assigned_to = new_user
        reassigned = True

    submitter_user = User.objects.filter(email=ticket.submitter_email).first()
    is_internal = is_helpdesk_staff(submitter_user, ticket.ticket_form.organization_id)
    user_is_staff = is_helpdesk_staff(request.user, ticket.ticket_form.organization_id)
    closed_statuses = [Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS, Ticket.DUPLICATE_STATUS]

    # Handling public-side updates
    if not user_is_staff and ticket.status == Ticket.REPLIED_STATUS and ticket.status == new_status:
        f.new_status = ticket.status = new_status = Ticket.OPEN_STATUS
        ticket.save()
        f.save()

    if new_status != ticket.status:  # Manually setting status to New, Open, Replied, Resolved, Closed, or Duplicate
        ticket.status = new_status
        f.new_status = new_status
        if f.title:
            f.title += ' and %s' % ticket.get_status_display()
        else:
            f.title = '%s' % ticket.get_status_display()
    elif comment and not user_is_staff and ticket.status in closed_statuses:
        # If a non-staff user, set status to Open/Reopened
        f.new_status = ticket.status = Ticket.REOPENED_STATUS
        f.save()

    if not f.title:
        if f.comment:
            f.title = _('Comment')
        else:
            f.title = _('Updated')

    ticket.save()
    f.save()

    files = []
    if request.FILES:
        files = process_attachments(f, request.FILES.getlist('attachment'))

    if title and title != ticket.title:
        c = TicketChange(
            followup=f,
            field=_('Title'),
            old_value=ticket.title,
            new_value=title,
        )
        c.save()
        ticket.title = title

    if new_status != old_status:
        c = TicketChange(
            followup=f,
            field=_('Status'),
            old_value=old_status_str,
            new_value=ticket.get_status_display(),
        )
        c.save()

    if ticket.assigned_to != old_owner:
        old_name = new_name = "no one"
        if old_owner:
            old_name = old_owner.get_full_name() or old_owner.get_username()
        if ticket.assigned_to:
            new_name = ticket.assigned_to.get_full_name() or ticket.assigned_to.get_username()
        c = TicketChange(
            followup=f,
            field=_('Owner'),
            old_value=old_name,
            new_value=new_name,
        )
        c.save()

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
        old_value = ticket.due_date.astimezone(timezone.get_current_timezone()).strftime(CUSTOMFIELD_DATETIME_FORMAT) if ticket.due_date else 'None'
        new_value = due_date.astimezone(timezone.get_current_timezone()).strftime(CUSTOMFIELD_DATETIME_FORMAT) if due_date else 'None'
        c = TicketChange(
            followup=f,
            field=_('Due on'),
            old_value=old_value,
            new_value=new_value,
        )
        c.save()
        ticket.due_date = due_date

    if new_status in (Ticket.RESOLVED_STATUS, Ticket.CLOSED_STATUS):
        if new_status == Ticket.RESOLVED_STATUS or ticket.resolution is None:
            ticket.resolution = comment

    # ticket might have changed above, so we re-instantiate context with the
    # (possibly) updated ticket.
    context = safe_template_context(ticket)
    context.update(
        resolution=ticket.resolution,
        comment=f.comment,
        private=(not public),
    )
    """
    Begin emailing updates to users.
    If public:
        - submitter
        - cc_public
        - extra
    Always:
        - queue_updated (if there's a queue updated user)
        - assigned_user (if there's an assigned user)
        - cc_users
    Never:
        - queue_new
    """

    messages_sent_to = set()
    try:
        messages_sent_to.add(request.user.email)
    except AttributeError:
        pass

    # Emails an update to the owner
    if reassigned:
        template_staff = 'assigned_owner'  # reassignment template
    elif f.new_status == Ticket.RESOLVED_STATUS:
        template_staff = 'resolved_owner'
    elif f.new_status == Ticket.CLOSED_STATUS:
        template_staff = 'closed_owner'
    else:
        template_staff = 'updated_owner'

    if ticket.assigned_to and (not no_changes_excluding_time_spent) and (
        ticket.assigned_to.usersettings_helpdesk.email_on_ticket_change
        or (reassigned and ticket.assigned_to.usersettings_helpdesk.email_on_ticket_assigned)
    ):
        messages_sent_to.update(
            ticket.send_ticket_mail(    # sends the assigned/resolved/closed/updated_owner template to the owner.
                {'assigned_to': (template_staff, context)},
                organization=ticket.ticket_form.organization,
                dont_send_to=messages_sent_to,
                fail_silently=True,
                files=files,
                user=None if not is_helpdesk_staff(request.user, ticket.ticket_form.organization_id) else request.user,
                source='updated (owner)'
            )
        )

    # Send an email about the reassignment to the previously assigned user
    if old_owner and reassigned and old_owner.email not in messages_sent_to:
        send_templated_mail(
            template_name='assigned_cc_user',
            context=context,
            recipients=[old_owner.email],
            sender=ticket.queue.from_address,
            fail_silently=True,
            organization=ticket.ticket_form.organization,
            user=None if not is_helpdesk_staff(request.user, ticket.ticket_form.organization_id) else request.user,
            source='updated (reassigned owner)',
            ticket_id=ticket.pk
        )

    # Emails an update to users who follow all ticket updates.
    if reassigned:
        template_cc = 'assigned_cc_user'  # reassignment template
    elif f.new_status == Ticket.RESOLVED_STATUS:
        template_cc = 'resolved_cc_user'
    elif f.new_status == Ticket.CLOSED_STATUS:
        template_cc = 'closed_cc_user'
    else:
        template_cc = 'updated_cc_user'

    if not no_changes_excluding_time_spent:
        messages_sent_to.update(
            ticket.send_ticket_mail(
                {'queue_updated': (template_cc, context),
                 'cc_users': (template_cc, context)},
                organization=ticket.ticket_form.organization,
                dont_send_to=messages_sent_to,
                fail_silently=True,
                files=files,
                user=None if not is_helpdesk_staff(request.user, ticket.ticket_form.organization_id) else request.user,
                source="updated (CC'd staff)"
            ))

        # Public users (submitter, public CC, and extra_field emails) are only updated if there's a new status or a comment.
        if public and (
                (f.comment and not no_changes_excluding_time_spent)
                or
                (f.new_status in (Ticket.RESOLVED_STATUS, Ticket.CLOSED_STATUS))):
            if f.new_status == Ticket.RESOLVED_STATUS:
                template = 'resolved_'
            elif f.new_status == Ticket.CLOSED_STATUS:
                template = 'closed_'
            else:
                template = 'updated_'

            roles = {
                'submitter': (template + 'submitter', context),
                'cc_public': (template + 'cc_public', context),
                'extra': (template + 'cc_public', context),
            }
            # todo is this necessary?
            if is_internal:
                roles['submitter'] = (template + 'cc_user', context)

            messages_sent_to.update(
                ticket.send_ticket_mail(
                    roles,
                    organization=ticket.ticket_form.organization,
                    dont_send_to=messages_sent_to,
                    fail_silently=True,
                    files=files,
                    user=None if not is_helpdesk_staff(request.user, ticket.ticket_form.organization_id) else request.user,
                    source='updated (public)'
                ))

    ticket.save()

    # auto subscribe user if enabled
    if helpdesk_settings.HELPDESK_AUTO_SUBSCRIBE_ON_TICKET_RESPONSE and request.user.is_authenticated:
        ticketcc_string, SHOW_SUBSCRIBE = return_ticketccstring_and_show_subscribe(request.user, ticket)
        if SHOW_SUBSCRIBE:
            subscribe_staff_member_to_ticket(ticket, request.user)

    return return_to_ticket(request.user, request, helpdesk_settings, ticket)


def return_to_ticket(user, request, helpdesk_settings, ticket):
    """Helper function for update_ticket"""
    huser = HelpdeskUser(user, request)
    if is_helpdesk_staff(user) and huser.can_access_ticket(ticket):
        return HttpResponseRedirect(ticket.get_absolute_url())
    else:
        return HttpResponseRedirect(ticket.ticket_url)


@helpdesk_staff_member_required
def mass_update(request):
    tickets = request.POST.get('selected_ids')
    action = request.POST.get('action', None)
    if not (tickets and action):
        return HttpResponseRedirect(reverse('helpdesk:list'))
    tickets = tickets.split(',')

    if action.startswith('assign_'):
        parts = action.split('_')
        user = User.objects.get(id=parts[1])
        action = 'assign'
    if action == 'kbitem_none':
        kbitem = None
        action = 'set_kbitem'
    if action.startswith('kbitem_'):
        parts = action.split('_')
        kbitem = KBItem.objects.get(id=parts[1])
        action = 'set_kbitem'
    elif action == 'take':
        user = request.user
        action = 'assign'
    elif action == 'merge':
        # Redirect to the Merge View with selected tickets id in the GET request
        return redirect(
            reverse('helpdesk:merge_tickets') + '?' + '&'.join(['tickets=%s' % ticket_id for ticket_id in tickets])
        )
    elif action == 'export':
        return export_ticket_table(request, tickets)

    huser = HelpdeskUser(request.user)
    for t in Ticket.objects.filter(id__in=tickets):
        if not huser.can_access_queue(t.queue):
            continue

        if action == 'assign' and t.assigned_to != user:
            t.assigned_to = user
            t.save()
            f = FollowUp(ticket=t,
                         date=timezone.now(),
                         title=_('Assigned to %(username)s in bulk update' % {
                             'username': user.get_full_name() or user.get_username()
                         }),
                         public=False,  # DC
                         user=request.user)
            f.save()
        elif action == 'unassign' and t.assigned_to is not None:
            t.assigned_to = None
            t.save()
            f = FollowUp(ticket=t,
                         date=timezone.now(),
                         title=_('Unassigned in bulk update'),
                         public=False,  # DC
                         user=request.user)
            f.save()
        elif action == 'set_kbitem':
            t.kbitem = kbitem
            t.save()
            f = FollowUp(ticket=t,
                         date=timezone.now(),
                         title=_('KBItem set in bulk update'),
                         public=False,
                         user=request.user)
            f.save()
        elif action == 'close' and t.status != Ticket.CLOSED_STATUS:
            t.status = Ticket.CLOSED_STATUS
            t.save()
            f = FollowUp(ticket=t,
                         date=timezone.now(),
                         title=_('Closed in bulk update'),
                         public=False,
                         user=request.user,
                         new_status=Ticket.CLOSED_STATUS)
            f.save()
            if t.queue.reassign_when_closed and t.queue.default_owner:
                new_user = t.queue.default_owner
                f.title += ' and Assigned to %(name)s' % {
                    'name': new_user.get_full_name() or new_user.get_username(),
                }
                t.assigned_to = new_user
                f.save()
                t.save()
        elif action == 'close_public' and t.status != Ticket.CLOSED_STATUS:
            t.status = Ticket.CLOSED_STATUS
            t.save()
            f = FollowUp(ticket=t,
                         date=timezone.now(),
                         title=_('Closed in bulk update'),
                         public=True,
                         user=request.user,
                         new_status=Ticket.CLOSED_STATUS)
            f.save()
            if t.queue.reassign_when_closed and t.queue.default_owner:
                new_user = t.queue.default_owner
                old_user = t.assigned_to
                f.title += ' and Assigned to %(name)s' % {
                    'name': new_user.get_full_name() or new_user.get_username(),
                }
                t.assigned_to = new_user
                f.save()
                t.save()

            # Send email to Submitter, Queue CC, CC'd Users, CC'd Public, Extra Fields, and Owner
            context = safe_template_context(t)
            context.update(resolution=t.resolution,
                           queue=queue_template_context(t.queue),
                           private=False)

            messages_sent_to = set()
            try:
                messages_sent_to.add(request.user.email)
            except AttributeError:
                pass

            roles = {
                'submitter': ('closed_submitter', context),
                'queue_updated': ('closed_cc_user', context),
                'cc_users': ('closed_cc_user', context),
                'cc_public': ('closed_cc_public', context),
                'extra': ('closed_cc_public', context),
            }
            if t.assigned_to and t.assigned_to.usersettings_helpdesk.email_on_ticket_change:
                roles['assigned_to'] = ('closed_owner', context)

            messages_sent_to.update(
                t.send_ticket_mail(
                    roles,
                    organization=t.ticket_form.organization,
                    dont_send_to=messages_sent_to,
                    fail_silently=True,
                    user=None if not is_helpdesk_staff(request.user, t.ticket_form.organization_id) else request.user,
                    source='bulk (closed)'
                )
            )
            if t.queue.reassign_when_closed and t.queue.default_owner and old_user and old_user.email not in messages_sent_to:
                send_templated_mail(
                    template_name='closed_owner',
                    context=context,
                    recipients=[old_user.email],
                    sender=t.queue.from_address,
                    fail_silently=True,
                    organization=t.ticket_form.organization,
                    user=None if not is_helpdesk_staff(request.user, t.ticket_form.organization_id) else request.user,
                    source='bulk (closed and auto-reassigned)',
                    ticket_id=t.pk
                )

        elif action == 'delete':
            # todo create a note of this somewhere?
            t.delete()

    return HttpResponseRedirect(reverse('helpdesk:list'))


mass_update = staff_member_required(mass_update)


# Prepare ticket attributes which will be displayed in the table to choose which value to keep when merging
# commented out are duplicate with customfields TODO delete later
ticket_attributes = (
    ('created', _('Created date')),
    # ('due_date', _('Due on')),
    ('get_status_display', _('Status')),
    # ('submitter_email', _('Submitter email')),
    ('assigned_to', _('Owner')),
    # ('description', _('Description')),
    ('resolution', _('Resolution')),
)


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
        custom_fields = CustomField.objects.filter(ticket_form_id__in=list(tickets.values_list('ticket_form__id'))
                                                   ).order_by('field_name').distinct('field_name').exclude(
                    field_name__in=['cc_emails', 'attachment', 'queue']
                )

        default = _('Not defined')
        for ticket in tickets:
            ticket.values = {}
            # Prepare the value for each attribute of this ticket
            for attribute, display_name in ticket_attributes:
                if attribute.startswith('get_') and attribute.endswith('_display'):
                    # Hack to call methods like get_FIELD_display()
                    value = getattr(ticket, attribute, default)()
                else:
                    value = getattr(ticket, attribute, default)
                ticket.values[attribute] = {
                    'value': value,
                    'checked': str(ticket.id) == request.POST.get(attribute)
                }
            # Prepare the value for each custom fields of this ticket
            for custom_field in custom_fields:
                try:
                    value = getattr(ticket, custom_field.field_name)
                except AttributeError:
                    # Search in extra_data
                    if custom_field.field_name in ticket.extra_data.keys():
                        value = ticket.extra_data[custom_field.field_name]
                    else:
                        value = default
                ticket.values[custom_field.field_name] = {
                    'value': value,
                    'checked': str(ticket.id) == request.POST.get(custom_field.field_name)
                }

        if request.method == 'POST':
            # Find which ticket has been chosen to be the main one
            try:
                chosen_ticket = tickets.get(id=request.POST.get('chosen_ticket'))
            except Ticket.DoesNotExist:
                ticket_select_form.add_error(
                    field='tickets',
                    error=_('Please choose a ticket in which the others will be merged into.')
                )
            else:
                # Save ticket fields values
                for attribute, display_name in ticket_attributes:
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
                        # Get value from selected ticket and then save it on the chosen ticket
                        value = getattr(selected_ticket, attribute)
                        setattr(chosen_ticket, attribute, value)
                # Save custom fields values
                for custom_field in custom_fields:
                    id_for_custom_field = request.POST.get(custom_field.field_name)
                    if id_for_custom_field != chosen_ticket.id:
                        try:
                            selected_ticket = tickets.get(id=id_for_custom_field)
                        except (Ticket.DoesNotExist, ValueError):
                            continue
                        try:
                            value = getattr(selected_ticket, custom_field.field_name)
                            setattr(chosen_ticket, custom_field.field_name, value)
                        except AttributeError:
                            # Search in extra_data
                            if custom_field.field_name in ticket.extra_data.keys():
                                value = selected_ticket.extra_data[custom_field.field_name]
                            else:
                                value = default
                            chosen_ticket.extra_data[custom_field.field_name] = value

                # Save changes
                chosen_ticket.save()

                # For other tickets, save the link to the ticket in which they have been merged to
                # and set status to DUPLICATE
                for ticket in tickets.exclude(id=chosen_ticket.id):
                    ticket.merged_to = chosen_ticket
                    ticket.status = Ticket.DUPLICATE_STATUS
                    ticket.save()

                    # Send mail to submitter email and ticket CC to let them know ticket has been merged
                    context = safe_template_context(ticket)
                    context['private'] = False
                    if ticket.submitter_email:
                        send_templated_mail(
                            template_name='merged',
                            context=context,
                            recipients=[ticket.submitter_email],
                            bcc=[cc.email_address for cc in ticket.ticketcc_set.select_related('user')],
                            sender=ticket.queue.from_address,
                            fail_silently=True,
                            organization=ticket.ticket_form.organization,
                            user=None if not is_helpdesk_staff(request.user, ticket.ticket_form.organization_id) else request.user,
                            source='merging',
                            ticket_id=chosen_ticket.pk
                        )

                    # Move all followups and update their title to know they come from another ticket
                    ticket.followup_set.update(
                        ticket=chosen_ticket,
                        title=_(('[Merged from #%(id)d] %(title)s') % {'id': ticket.id, 'title': ticket.title})[:200],
                    )

                    # Move all emails to the chosen ticket
                    ticket.emails.update(ticket_id=chosen_ticket.id)

                    # Add submitter_email, assigned_to email and ticketcc to chosen ticket if necessary
                    chosen_ticket.add_email_to_ticketcc_if_not_in(email=ticket.submitter_email)
                    if ticket.assigned_to and ticket.assigned_to.email:
                        chosen_ticket.add_email_to_ticketcc_if_not_in(email=ticket.assigned_to.email)
                    for ticketcc in ticket.ticketcc_set.all():
                        chosen_ticket.add_email_to_ticketcc_if_not_in(ticketcc=ticketcc)
                return redirect(chosen_ticket)

    return render(request, 'helpdesk/ticket_merge.html', {
        'tickets': tickets,
        'ticket_attributes': ticket_attributes,
        'custom_fields': custom_fields,
        'ticket_select_form': ticket_select_form,
        'debug': settings.DEBUG,
    })


@helpdesk_staff_member_required
def ticket_list(request):
    context = {}

    huser = HelpdeskUser(request.user)
    org = request.user.default_organization.helpdesk_organization

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
            'status__in': [Ticket.OPEN_STATUS, Ticket.REOPENED_STATUS, Ticket.REPLIED_STATUS, Ticket.NEW_STATUS],
        },
        'sorting': 'created',
        'sortreverse': False,
        'search_string': '',
    }

    # If the user is coming from the header/navigation search box, lets' first
    # look at their query to see if they have entered a valid ticket number. If
    # they have, just redirect to that ticket number. Otherwise, we treat it as
    # a keyword search.

    if request.GET.get('search_type', None) == 'header':
        query = request.GET.get('q')
        filter = None
        if query.find('-') > 0:
            try:
                queue, id = Ticket.queue_and_id_from_query(query)
                id = int(id)
            except ValueError:
                id = None

            if id:
                filter = {'queue__slug': queue, 'id': id}
        else:
            try:
                query = int(query)
            except ValueError:
                query = None

            if query:
                filter = {'id': int(query)}

        if filter:
            try:
                ticket = huser.get_tickets_in_queues().get(**filter)
                return HttpResponseRedirect(ticket.staff_url)
            except Ticket.DoesNotExist:
                # Go on to standard keyword searching
                pass

    try:
        saved_query, query_params = load_saved_query(request, query_params)
    except QueryLoadError:
        return HttpResponseRedirect(reverse('helpdesk:list'))

    filter_in_params = dict([
        ('queue', 'queue__id__in'),
        ('assigned_to', 'assigned_to__id__in'),
        ('status', 'status__in'),
        ('kbitem', 'kbitem__in'),
        ('submitter', 'submitter_email__in'),
    ])
    filter_null_params = dict([
        ('queue', 'queue__id__isnull'),
        ('assigned_to', 'assigned_to__id__isnull'),
        ('status', 'status__isnull'),
        ('kbitem', 'kbitem__isnull'),
        ('submitter', 'submitter_email__isnull'),
    ])

    if saved_query:
        pass
    elif not {'queue', 'assigned_to', 'status', 'q', 'sort', 'sortreverse', 'kbitem', 'submitter'}.intersection(request.GET):
        # Fall-back if no querying is being done
        query_params = deepcopy(default_query_params)
    else:
        for param, filter_command in filter_in_params.items():
            if not request.GET.get(param) is None:
                patterns = request.GET.getlist(param)
                try:
                    pattern_pks = [int(pattern) for pattern in patterns]
                    if -1 in pattern_pks:
                        query_params['filtering'][filter_null_params[param]] = True
                    else:
                        query_params['filtering'][filter_command] = pattern_pks
                except ValueError:
                    pass

        date_from = request.GET.get('date_from')
        if date_from:
            query_params['filtering']['created__gte'] = date_from

        date_to = request.GET.get('date_to')
        if date_to:
            query_params['filtering']['created__lte'] = date_to

        last_reply_from = request.GET.get('last_reply_from')
        if last_reply_from:
            query_params['filtering']['last_reply__gte'] = last_reply_from

        last_reply_to = request.GET.get('last_reply_to')
        if last_reply_to:
            query_params['filtering']['last_reply__lte'] = last_reply_to

        paired_count_from = request.GET.get('paired_count_from')
        if paired_count_from:
            query_params['filtering']['paired_count__gte'] = paired_count_from

        paired_count_to = request.GET.get('paired_count_to')
        if paired_count_to:
            query_params['filtering']['paired_count__lte'] = paired_count_to

        # KEYWORD SEARCHING
        q = request.GET.get('q', '')
        context['query'] = q
        query_params['search_string'] = q

        # SORTING
        sort = request.GET.get('sort', None)
        if sort not in ('status', 'assigned_to', 'created', 'title', 'queue', 'priority', 'kbitem', 'submitter',
                        'paired_count'):
            sort = 'created'
        query_params['sorting'] = sort

        sortreverse = request.GET.get('sortreverse', None)
        query_params['sortreverse'] = sortreverse

    urlsafe_query = query_to_base64(query_params)
    Query(huser, base64query=urlsafe_query).refresh_query()

    # Return queries that the user created, or that have been shared with everyone and the user hasn't rejected
    user_saved_queries = SavedSearch.objects.filter(Q(user=request.user)
                                                    | (Q(shared__exact=True) & ~Q(opted_out_users__in=[request.user])))

    search_message = ''
    if query_params['search_string'] and settings.DATABASES['default']['ENGINE'].endswith('sqlite'):
        search_message = _(
            '<p><strong>Note:</strong> Your keyword search is case sensitive '
            'because of your database. This means the search will <strong>not</strong> '
            'be accurate. By switching to a different database system you will gain '
            'better searching! For more information, read the '
            '<a href="http://docs.djangoproject.com/en/dev/ref/databases/#sqlite-string-matching">'
            'Django Documentation on string matching in SQLite</a>.')

    # Get KBItems that are part of the user's helpdesk_organization
    kbitem_choices = [(item.pk, str(item)) for item in KBItem.objects.filter(
        category__organization=org)]

    # After query is run, replaces null-filters with in-filters=[-1], so page can properly display that filter.
    for param, null_query in filter_null_params.items():
        popped = query_params['filtering'].pop(null_query, None)
        if popped is not None:
            query_params['filtering'][filter_in_params[param]] = [-1]

    user_choices = list_of_helpdesk_staff(org)

    # Get extra data columns to be displayed if only 1 queue is selected
    extra_data_columns = {}
    if len(query_params['filtering'].get('queue__id__in', [])) == 1:
        extra_data_columns = get_extra_data_columns(query_params['filtering']['queue__id__in'][0])

    json_queries = {i['id']: i for i in user_saved_queries.values('id', 'user_id', 'shared')}

    return render(request, 'helpdesk/ticket_list.html', dict(
        context,
        default_tickets_per_page=request.user.usersettings_helpdesk.tickets_per_page,
        user_choices=user_choices,
        kb_items=KBItem.objects.all(),
        queue_choices=huser.get_queues(),
        status_choices=Ticket.STATUS_CHOICES,
        kbitem_choices=kbitem_choices,
        urlsafe_query=urlsafe_query,
        user_saved_queries=user_saved_queries,
        json_queries=json.dumps(json_queries),
        query_params=query_params,
        from_saved_query=saved_query is not None,
        saved_query=saved_query,
        search_message=search_message,
        extra_data_columns=extra_data_columns,
        debug=settings.DEBUG,
    ))


ticket_list = staff_member_required(ticket_list)


class QueryLoadError(Exception):
    pass


def load_saved_query(request, query_params=None):
    saved_query = None

    if request.GET.get('saved_query', None):
        try:
            saved_query = SavedSearch.objects.get(
                Q(pk=request.GET.get('saved_query')) &
                ((Q(shared=True) & ~Q(opted_out_users__in=[request.user])) | Q(user=request.user))
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
    return (saved_query, query_params)


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
    return (JsonResponse(query.get_timeline_context(), status=status.HTTP_200_OK))


@helpdesk_staff_member_required
def edit_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    perm = ticket_perm_check(request, ticket)
    if perm is not None:
        return perm

    form = EditTicketForm(request.POST or None, instance=ticket)
    if form.is_valid():
        ticket = form.save()
        return redirect(ticket)

    return render(request, 'helpdesk/edit_ticket.html', {'form': form, 'ticket': ticket, 'errors': form.errors, 'debug': settings.DEBUG})


edit_ticket = staff_member_required(edit_ticket)


class CreateTicketView(MustBeStaffMixin, abstract_views.AbstractCreateTicketMixin, FormView):
    template_name = 'helpdesk/create_ticket.html'
    form_class = TicketForm
    form_id = None

    def get_initial(self):
        initial_data = super().get_initial()
        return initial_data

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        queues = HelpdeskUser(self.request.user, self.request).get_queues()
        kwargs["queue_choices"] = _get_queue_choices(queues)
        kwargs['form_id'] = self.form_id
        return kwargs

    def form_valid(self, form):
        self.ticket = form.save(form_id=self.form_id, user=self.request.user if self.request.user.is_authenticated else None)
        return super().form_valid(form)

    def get_success_url(self):
        request = self.request
        if HelpdeskUser(request.user, request).can_access_queue(self.ticket.queue):
            return self.ticket.get_absolute_url()
        else:
            return reverse('helpdesk:dashboard')


@helpdesk_staff_member_required
def raw_details(request, type):
    # TODO: This currently only supports spewing out 'PreSetReply' objects,
    # in the future it needs to be expanded to include other items. All it
    # does is return a plain-text representation of an object.

    if type not in ('preset',):
        raise Http404

    if type == 'preset' and request.GET.get('id', False):
        try:
            preset = PreSetReply.objects.get(id=request.GET.get('id'))
            return HttpResponse(preset.body)
        except PreSetReply.DoesNotExist:
            raise Http404

    raise Http404


raw_details = staff_member_required(raw_details)


@helpdesk_staff_member_required
def hold_ticket(request, ticket_id, unhold=False):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    perm = ticket_perm_check(request, ticket)
    if perm is not None:
        return perm

    if unhold:
        ticket.on_hold = False
        title = _('Ticket taken off hold')
    else:
        ticket.on_hold = True
        title = _('Ticket placed on hold')

    f = FollowUp(
        ticket=ticket,
        user=request.user,
        title=title,
        date=timezone.now(),
        public=True,
    )
    f.save()

    ticket.save()

    return HttpResponseRedirect(ticket.get_absolute_url())


hold_ticket = staff_member_required(hold_ticket)


@helpdesk_staff_member_required
def unhold_ticket(request, ticket_id):
    return hold_ticket(request, ticket_id, unhold=True)


unhold_ticket = staff_member_required(unhold_ticket)


@helpdesk_staff_member_required
def rss_list(request):
    return render(request, 'helpdesk/rss_list.html', {'queues': Queue.objects.all(), 'debug': settings.DEBUG})


rss_list = staff_member_required(rss_list)


@helpdesk_staff_member_required
def report_index(request):
    huser = HelpdeskUser(request.user)
    user_queues = huser.get_queues()
    Tickets = Ticket.objects.filter(queue__in=user_queues)
    number_tickets = Tickets.count()
    saved_query = request.GET.get('saved_query', None)

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
        'debug': settings.DEBUG,
    })


report_index = staff_member_required(report_index)


@helpdesk_staff_member_required
def run_report(request, report):
    if Ticket.objects.all().count() == 0 or report not in (
            'queuemonth', 'usermonth', 'queuestatus', 'queuepriority', 'userstatus',
            'userpriority', 'userqueue', 'daysuntilticketclosedbymonth'):
        return HttpResponseRedirect(reverse("helpdesk:report_index"))

    report_queryset = Ticket.objects.all().select_related().filter(
        queue__in=HelpdeskUser(request.user).get_queues()
    )

    try:
        saved_query, query_params = load_saved_query(request)
    except QueryLoadError:
        return HttpResponseRedirect(reverse('helpdesk:report_index'))

    if request.GET.get('saved_query', None):
        Query(report_queryset, query_to_base64(query_params))

    from collections import defaultdict
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

        summarytable[metric1, metric2] += 1
        if metric3:
            if report == 'daysuntilticketclosedbymonth':
                summarytable2[metric1, metric2] += metric3

    table = []

    if report == 'daysuntilticketclosedbymonth':
        for key in summarytable2.keys():
            summarytable[key] = summarytable2[key] / summarytable[key]

    header1 = sorted(set(list(i for i, _ in summarytable.keys())))

    column_headings = [col1heading] + possible_options

    # Prepare a dict to store totals for each possible option
    totals = {}
    # Pivot the data so that 'header1' fields are always first column
    # in the row, and 'possible_options' are always the 2nd - nth columns.
    for item in header1:
        data = []
        for hdr in possible_options:
            if hdr not in totals.keys():
                totals[hdr] = summarytable[item, hdr]
            else:
                totals[hdr] += summarytable[item, hdr]
            data.append(summarytable[item, hdr])
        table.append([item] + data)

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
        'debug': settings.DEBUG,
    })


run_report = staff_member_required(run_report)


@helpdesk_staff_member_required
def save_query(request):
    title = request.POST.get('title', None)
    shared = request.POST.get('shared', False)
    visible_cols = request.POST.get('visible', '').split(',')

    if shared == 'on':  # django only translates '1', 'true', 't' into True
        shared = True
    query_encoded = request.POST.get('query_encoded', None)

    if not title or not query_encoded:
        return HttpResponseRedirect(reverse('helpdesk:list'))

    query_unencoded = query_from_base64(query_encoded)
    query_unencoded['visible_cols'] = visible_cols
    query_encoded = query_to_base64(query_unencoded)

    query = SavedSearch(title=title, shared=shared, query=query_encoded, user=request.user)
    query.save()

    return HttpResponseRedirect('%s?saved_query=%s' % (reverse('helpdesk:list'), query.id))


save_query = staff_member_required(save_query)


@helpdesk_staff_member_required
def delete_saved_query(request, id):
    query = get_object_or_404(SavedSearch, id=id, user=request.user)

    if request.method == 'POST':
        query.delete()
        return HttpResponseRedirect(reverse('helpdesk:list'))
    else:
        return render(request, 'helpdesk/confirm_delete_saved_query.html', {'query': query, 'debug': settings.DEBUG})


delete_saved_query = staff_member_required(delete_saved_query)


@helpdesk_staff_member_required
def reject_saved_query(request, id):
    user = request.user
    query = get_object_or_404(SavedSearch, id=id)

    query.opted_out_users.add(user)
    return HttpResponseRedirect(reverse('helpdesk:list'))


reject_saved_query = staff_member_required(reject_saved_query)


@helpdesk_staff_member_required
def reshare_saved_query(request, id):
    user = request.user
    query = get_object_or_404(SavedSearch, id=id, user=user)

    query.opted_out_users.clear()
    query.shared = True
    query.save()
    return HttpResponseRedirect(reverse('helpdesk:list') + '?saved_query=%s' % query.id)


reject_saved_query = staff_member_required(reject_saved_query)


@helpdesk_staff_member_required
def unshare_saved_query(request, id):
    user = request.user
    query = get_object_or_404(SavedSearch, id=id, user=user)

    query.shared = False
    query.save()
    return HttpResponseRedirect(reverse('helpdesk:list') + '?saved_query=%s' % query.id)


reject_saved_query = staff_member_required(reject_saved_query)


class EditUserSettingsView(MustBeStaffMixin, UpdateView):
    template_name = 'helpdesk/user_settings.html'
    form_class = UserSettingsForm
    model = UserSettings
    success_url = reverse_lazy('helpdesk:dashboard')

    def get_object(self):
        return UserSettings.objects.get_or_create(user=self.request.user)[0]


@helpdesk_superuser_required
def email_ignore(request):
    return render(request, 'helpdesk/email_ignore_list.html', {
        'ignore_list': IgnoreEmail.objects.all(),
        'debug': settings.DEBUG,
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

    return render(request, 'helpdesk/email_ignore_add.html', {'form': form, 'debug': settings.DEBUG})


email_ignore_add = superuser_required(email_ignore_add)


@helpdesk_superuser_required
def email_ignore_del(request, id):
    ignore = get_object_or_404(IgnoreEmail, id=id)
    if request.method == 'POST':
        ignore.delete()
        return HttpResponseRedirect(reverse('helpdesk:email_ignore'))
    else:
        return render(request, 'helpdesk/email_ignore_del.html', {'ignore': ignore, 'debug': settings.DEBUG})


email_ignore_del = superuser_required(email_ignore_del)


@helpdesk_staff_member_required
def ticket_cc(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    perm = ticket_perm_check(request, ticket)
    if perm is not None:
        return perm

    copies_to = ticket.ticketcc_set.all()
    return render(request, 'helpdesk/ticket_cc_list.html', {
        'copies_to': copies_to,
        'ticket': ticket,
        'debug': settings.DEBUG,
    })


ticket_cc = staff_member_required(ticket_cc)


@helpdesk_staff_member_required
def ticket_cc_add(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    perm = ticket_perm_check(request, ticket)
    if perm is not None:
        return perm

    form = None
    if request.method == 'POST':
        form = TicketCCForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data.get('user')
            email = form.cleaned_data.get('email')
            if user and ticket.ticketcc_set.filter(user=user).exists():
                form.add_error('user', _('Impossible to add twice the same user'))
            elif user and user.email and ticket.ticketcc_set.filter(email=user.email).exists():
                form.add_error('user', _('Impossible to add twice the same email address'))
            elif email and ticket.ticketcc_set.filter(email=email).exists():
                form.add_error('email', _('Impossible to add twice the same email address'))
            else:
                ticketcc = form.save(commit=False)
                ticketcc.ticket = ticket
                if user and user.email:
                    ticketcc.email = user.email
                ticketcc.save()
                return HttpResponseRedirect(reverse('helpdesk:ticket_cc', kwargs={'ticket_id': ticket.id}))

    # Add list of users to the TicketCCUserForm
    users = list_of_helpdesk_staff(ticket.ticket_form.organization)
    users = users.order_by(User.USERNAME_FIELD)

    form_user = TicketCCUserForm()
    form_user.fields['user'].choices = [('', '--------')] + [
        (u.id, (u.get_full_name() or u.get_username())) for u in users]

    return render(request, 'helpdesk/ticket_cc_add.html', {
        'ticket': ticket,
        'form': form,
        'form_email': TicketCCEmailForm(),
        'form_user': form_user,
        'debug': settings.DEBUG,
    })


ticket_cc_add = staff_member_required(ticket_cc_add)


@helpdesk_staff_member_required
def ticket_cc_del(request, ticket_id, cc_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    cc = get_object_or_404(TicketCC, ticket__id=ticket_id, id=cc_id)

    if request.method == 'POST':
        cc.delete()
        return HttpResponseRedirect(reverse('helpdesk:ticket_cc', kwargs={'ticket_id': cc.ticket.id}))

    return render(request, 'helpdesk/ticket_cc_del.html', {'ticket': ticket, 'cc': cc, 'debug': settings.DEBUG})


ticket_cc_del = staff_member_required(ticket_cc_del)


@helpdesk_staff_member_required
def ticket_dependency_add(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    perm = ticket_perm_check(request, ticket)
    if perm is not None:
        return perm

    if request.method == 'POST':
        form = TicketDependencyForm(request.POST)
        if form.is_valid():
            ticketdependency = form.save(commit=False)
            ticketdependency.ticket = ticket
            if ticketdependency.ticket != ticketdependency.depends_on:
                ticketdependency.save()
            return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket.id]))
    else:
        form = TicketDependencyForm()
    return render(request, 'helpdesk/ticket_dependency_add.html', {
        'ticket': ticket,
        'form': form,
        'debug': settings.DEBUG,
    })


ticket_dependency_add = staff_member_required(ticket_dependency_add)


@helpdesk_staff_member_required
def ticket_dependency_del(request, ticket_id, dependency_id):
    dependency = get_object_or_404(TicketDependency, ticket__id=ticket_id, id=dependency_id)
    if request.method == 'POST':
        dependency.delete()
        return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket_id]))
    return render(request, 'helpdesk/ticket_dependency_del.html', {'dependency': dependency, 'debug': settings.DEBUG})


ticket_dependency_del = staff_member_required(ticket_dependency_del)


@helpdesk_staff_member_required
def attachment_del(request, ticket_id, attachment_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    perm = ticket_perm_check(request, ticket)
    if perm is not None:
        return perm

    attachment = get_object_or_404(FollowUpAttachment, id=attachment_id)
    if request.method == 'POST':
        attachment.delete()
        return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket_id]))
    return render(request, 'helpdesk/ticket_attachment_del.html', {
        'attachment': attachment,
        'filename': attachment.filename,
        'debug': settings.DEBUG,
    })


@helpdesk_staff_member_required
def beam_unpair(request, ticket_id, inventory_type, inventory_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    perm = ticket_perm_check(request, ticket)
    if perm is not None:
        return perm
    if inventory_type == 'property':
        prop = get_object_or_404(Property, id=inventory_id)
        ticket.beam_property.remove(prop)
    else:
        taxlot = get_object_or_404(TaxLot, id=inventory_id)
        ticket.beam_taxlot.remove(taxlot)

    return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket_id]))


def calc_average_nbr_days_until_ticket_resolved(Tickets):
    nbr_closed_tickets = Tickets.count()
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
    all_open_tickets = Tickets.exclude(status__in=[Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS, Ticket.DUPLICATE_STATUS])
    today = timezone.now()

    date_3 = date_rel_to_today(today, 3)
    date_7 = date_rel_to_today(today, 7)
    date_14 = date_rel_to_today(today, 14)
    date_30 = date_rel_to_today(today, 30)
    date_60 = date_rel_to_today(today, 60)
    date_3_str = date_3.strftime(CUSTOMFIELD_DATE_FORMAT)
    date_7_str = date_7.strftime(CUSTOMFIELD_DATE_FORMAT)
    date_14_str = date_14.strftime(CUSTOMFIELD_DATE_FORMAT)
    date_30_str = date_30.strftime(CUSTOMFIELD_DATE_FORMAT)
    date_60_str = date_60.strftime(CUSTOMFIELD_DATE_FORMAT)

    # > 0 & <= 3
    ota_le_3 = all_open_tickets.filter(created__gte=date_3)
    N_ota_le_3 = ota_le_3.count()

    # > 3 & <= 7
    ota_le_7_ge_3 = all_open_tickets.filter(created__gte=date_7, created__lt=date_3)
    N_ota_le_7_ge_3 = ota_le_7_ge_3.count()

    # > 7 & <= 14
    ota_le_14_ge_7 = all_open_tickets.filter(created__gte=date_14, created__lt=date_7)
    N_ota_le_14_ge_7 = ota_le_14_ge_7.count()

    # > 14
    ota_ge_14 = all_open_tickets.filter(created__lt=date_14)
    N_ota_ge_14 = ota_ge_14.count()

    # > 0 & <= 30
    ota_le_30 = all_open_tickets.filter(created__gte=date_30)
    N_ota_le_30 = ota_le_30.count()

    # >= 30 & <= 60
    ota_le_60_ge_30 = all_open_tickets.filter(created__gte=date_60, created__lte=date_30)
    N_ota_le_60_ge_30 = ota_le_60_ge_30.count()

    # >= 60
    ota_ge_60 = all_open_tickets.filter(created__lte=date_60)
    N_ota_ge_60 = ota_ge_60.count()

    # (O)pen (T)icket (S)tats
    ots = list()
    # label, number entries, color, sort_string
    ots.append(['Tickets < 3 days', N_ota_le_3, 'success',
                sort_string(date_3_str, ''), ])
    ots.append(['Tickets 4 - 7 days', N_ota_le_7_ge_3,
                'success' if N_ota_le_7_ge_3 == 0 else 'warning',
                sort_string(date_7_str, date_3_str), ])
    ots.append(['Tickets 8 - 14 days', N_ota_le_14_ge_7,
                'success' if N_ota_le_14_ge_7 == 0 else 'warning',
                sort_string(date_14_str, date_7_str), ])
#    ots.append(['Tickets 30 - 60 days', N_ota_le_60_ge_30,
#                'success' if N_ota_le_60_ge_30 == 0 else 'warning',
#                sort_string(date_60_str, date_30_str), ])
    ots.append(['Tickets > 14 days', N_ota_ge_14,
                'success' if N_ota_ge_14 == 0 else 'danger',
                sort_string('', date_14_str), ])

    # all closed tickets - independent of user.
    all_closed_tickets = Tickets.filter(status=Ticket.CLOSED_STATUS)
    average_nbr_days_until_ticket_closed = \
        calc_average_nbr_days_until_ticket_resolved(all_closed_tickets)
    # all closed tickets that were opened in the last 60 days.
    all_closed_last_60_days = all_closed_tickets.filter(created__gte=date_60)
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
    return 'sort=created&date_from=%s&date_to=%s&status=%s&status=%s&status=%s&status=%s' % (
        begin, end, Ticket.OPEN_STATUS, Ticket.REOPENED_STATUS, Ticket.REPLIED_STATUS, Ticket.NEW_STATUS)


@staff_member_required
def pair_property_milestone(request, ticket_id):
    """
    Prompt user to select one of the Ticket's paired property's milestone to pair Ticket to
    """
    from seed.models import Milestone,  Note, Pathway, PropertyView, PropertyMilestone

    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.method == 'POST':
        pv_id = request.POST.get('property_id', '').split('-')[1]
        milestone_id = request.POST.get('milestone_id').split('-')[1]

        pm = PropertyMilestone.objects.get(property_view_id=pv_id, milestone_id=milestone_id)

        # Create Note about pairing
        note_kwargs = {'organization_id': ticket.ticket_form.organization.id, 'user': request.user,
                       'name': 'Automatically Created', 'property_view': pm.property_view, 'note_type': Note.LOG,
                       'log_data': [{'model': 'PropertyMilestone', 'name': pm.milestone.name,
                                     'action': 'edited with the following:'},
                                    {'field': 'Milestone Paired Ticket',
                                     'previous_value': f'Ticket ID {pm.ticket.id if pm.ticket else "None"}',
                                     'new_value': f'Ticket ID {ticket.id}', 'state_id': pm.property_view.state.id},
                                    {'field': 'Implementation Status',
                                     'previous_value': pm.get_implementation_status_display(),
                                     'new_value': 'In Review', 'state_id': pm.property_view.state.id},
                                    {'field': 'Submission Date',
                                     'previous_value': pm.submission_date.strftime('%Y-%m-%d %H:%M:%S') if pm.submission_date else 'None',
                                     'new_value': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                                     'state_id': pm.property_view.state.id}
                                    ]
                       }
        Note.objects.create(**note_kwargs)

        pm.ticket = ticket
        pm.implementation_status = PropertyMilestone.MILESTONE_IN_REVIEW
        # Only set submission_date if it has never been set
        pm.submission_date = timezone.now() if pm.submission_date is None else pm.submission_date
        pm.save()

        return return_to_ticket(request.user, request, helpdesk_settings, ticket)

    properties = ticket.beam_property.all()

    # get all pathways attached to those properties and index them by property id
    # get all milestones for each pathway and index them by pathway id
    properties_per_cycle = {}
    pathways_per_property = {}
    milestones_per_pathway = {}
    for p in properties:
        views = PropertyView.objects.filter(property_id=p.id)
        for view in views:
            if view.cycle not in properties_per_cycle:
                properties_per_cycle[view.cycle] = [view]
            else:
                properties_per_cycle[view.cycle].append(view)

            pathways = Pathway.objects.filter(cycle_group__cyclegroupmapping__cycle_id=view.cycle.id)
            pathways_per_property[view.id] = pathways

            for pathway in pathways:
                milestones_per_pathway[pathway.id] = Milestone.objects.filter(pathwaymilestone__pathway_id=pathway.id,
                                                                              propertymilestone__property_view_id=view.id)
    return render(request, 'helpdesk/pair_property_milestone.html', {
        'ticket': ticket,
        'properties_per_cycle': properties_per_cycle,
        'pathways_per_property': pathways_per_property,
        'milestones_per_pathway': milestones_per_pathway,
        'debug': settings.DEBUG,
    })


def add_remove_label(org_id, user, payload, inventory_type):
    """

    """
    from seed.views.v3.label_inventories import LabelInventoryViewSet
    from django.http import QueryDict

    request = HttpRequest()
    request.method = 'PUT'
    request.query_params = QueryDict('organization_id='+str(org_id))
    request.user = user
    request.data = payload
    livs = LabelInventoryViewSet()
    livs.request = request
    ret = livs.put(request, inventory_type).data
    return ret


@staff_member_required
def edit_inventory_labels(request, inventory_type, ticket_id):
    """
    Prompt User to Add/Remove Labels from a Selected Paired Property
    """
    from seed.models import PropertyView, StatusLabel as Label, TaxLotView

    if inventory_type == 'property':
        view_class = PropertyView
        beam_inventories = 'beam_property'
    else:
        view_class = TaxLotView
        beam_inventories = 'beam_taxlot'

    ticket = get_object_or_404(Ticket, id=ticket_id)
    org_id = ticket.ticket_form.organization_id

    if request.method == 'POST':
        remove_ids = [i.replace('remove_', '') for i in request.POST.keys() if 'remove' in i]
        add_ids = [i.replace('add_', '') for i in request.POST.keys() if 'add' in i]

        pv_id = request.POST.get('inventory_id', '').split('-')[1]
        payload = {'inventory_ids': [pv_id], 'add_label_ids': add_ids, 'remove_label_ids': remove_ids}
        add_remove_label(org_id, request.user, payload, inventory_type)

        return return_to_ticket(request.user, request, helpdesk_settings, ticket)

    inventories = getattr(ticket, beam_inventories).all()

    labels_per_view = {}
    property_views_per_cycle = {}
    for inv in inventories:
        views = view_class.objects.filter(**{inventory_type + '_id': inv.id})
        for view in views:
            if view.cycle not in property_views_per_cycle:
                property_views_per_cycle[view.cycle] = [view]
            else:
                property_views_per_cycle[view.cycle].append(view)

            labels_per_view[view.id] = view.labels.all()

    labels = Label.objects.filter(super_organization_id=org_id)

    return render(request, 'helpdesk/edit_inventory_labels.html', {
        'ticket': ticket,
        'property_views_per_cycle': property_views_per_cycle,
        'labels_per_view': labels_per_view,
        'labels': labels,
        'inventory_type': inventory_type.capitalize(),
        'debug': settings.DEBUG,
    })


def export_ticket_table(request, tickets):
    """
    Export Tickets as they would be visible in the Ticket List
    """
    visible_cols = request.POST.get('visible').split(',')
    visible_cols.insert(2, 'title')  # Add title since it's concatenated in Front-End
    num_queues = request.POST.get('queue_length', '0')

    qs = Ticket.objects.filter(id__in=tickets)
    do_extra_data = int(num_queues) == 1

    return export(qs, DatatablesTicketSerializer, do_extra_data=do_extra_data, visible_cols=visible_cols)


@staff_member_required
def export_report(request):
    """
    Export Tickets in a report format. This is different from exporting from the TicketList  page which exports the
    table as it is
    """
    action = request.POST.get('action')
    paginate = action == 'export_year'  # TODO

    user_queue_ids = HelpdeskUser(request.user).get_queues().values_list('id', flat=True)
    qs = Ticket.objects.filter(queue_id__in=user_queue_ids
                               ).order_by('created', 'ticket_form'
                                          ).select_related('ticket_form__organization', 'assigned_to', 'queue',
                                                           ).prefetch_related('followup_set__user', 'beam_property')
    org = request.user.default_organization

    return export(qs, org, ReportTicketSerializer, paginate=paginate)


def export(qs, org, serializer, paginate=False, do_extra_data=True, visible_cols=[]):
    """
    Helper function for exporting the Ticket Table and for Reports. Lots of input variables describing which process
    :param qs: QuerySet of Tickets to Serialize and output to csv file.
    :param org: Organization object associated to all of the Forms
    :param serializer: Ticket Serializer to use on Queryset
    :param paginate:  TODO file into separate sheets for each year of tickets
    :param do_extra_data: Bool, process and save extra data fields to csv file
    :param visible_cols: List of visible cols to include in output
    :return: None, starts downloading the csv file
    """
    from collections import OrderedDict
    from helpdesk.serializers import ORG_TO_ID_FIELD_MAPPING

    ticket_form_ids = list(set(qs.values_list('ticket_form_id', flat=True)))
    building_id_org_field = None
    if org.name in ORG_TO_ID_FIELD_MAPPING:
        building_id_org_field = ORG_TO_ID_FIELD_MAPPING.get(org.name)

    # Fields that could be omitted from Form but still required a Display Name
    just_in_case_mapping = {
        'submitter_email': 'Submitter Email',
        'description': 'Description',
        'contact_name': 'Contact Name',
        'contact_email': 'Contact Email',
        'building_name': 'Building Name',
        'building_address': 'Building Address',
        'building_id': 'Building ID',
        'pm_id': 'Portfolio Manager ID',
        'title': 'Subject',
    }

    # Fields that either don't take a column or are generated by serializer
    other_mapping = {
        'last_reply': 'Last Reply',
        'status': 'Status',
        'paired_count': 'Number of Paired Tickets',
        'submitter': 'Submitter Email',
        'ticket': 'Ticket',
        'get_status': 'Ticket Status',
        'formtype': 'Ticket Form',
        'created': 'Created',
        'id': 'Ticket ID',
        'kbitem': 'Knowledgebase Item',
        'assigned_to': 'Assigned To',
        'time_spent': 'Time Spent',
        'merged_to': 'Merged To',
        'first_staff_followup': 'Date of First Staff Followup',
        'closed_date': 'Ticket Closed Date',
        'is_followup_required': 'Is Followup Required?',
        'number_staff_followups': 'Number of Staff Followups',
        'number_public_followups': 'Number of Public Followups',
        'property_type': 'Primary Property Type - Portfolio Manager-Calculated'
    }

    # Split tickets up into separate forms, serialize, and concatenate them
    report = pd.DataFrame()
    for ticket_form_id in ticket_form_ids:
        sub_qs = qs.filter(ticket_form_id=ticket_form_id)

        form = FormType.objects.get(id=ticket_form_id)
        data = serializer(sub_qs, many=True).data

        # Get extra data columns and their display names
        extra_data_cols = {}
        if do_extra_data:
            extra_data_cols = form.get_extra_fields_mapping()

        # Get Standard columns and their display names
        column_mapping = form.get_fields_mapping()
        mappings = {**column_mapping, **extra_data_cols, **other_mapping}
        mappings.update({k: v for k, v in just_in_case_mapping.items() if k not in mappings})  # Doesn't overwrite
        if mappings['building_id'] == 'Building ID' and building_id_org_field:
            mappings['building_id'] = building_id_org_field

        # Process Data
        output = []
        for row in data:
            # Move extra data from being a nested dict to being other fields
            extra_data = row.pop('extra_data')
            if do_extra_data:
                row.update(extra_data)

            # Get the data that is only visible
            if visible_cols:
                for col in list(set(row.keys()).difference(visible_cols)):
                    row.pop(col)

            # Replace Columns with their display names
            renamed_row = OrderedDict((mappings.get(k, k), v if v else '') for k, v in row.items())
            output.append(renamed_row)
        output = pd.json_normalize(output)
        report = report.append(output, ignore_index=True)
    report = report.set_index('Ticket ID')

    time_stamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    media_dir = 'helpdesk/reports/'
    file_name = f'ticket_export_{time_stamp}.csv'
    media_path = media_dir + file_name

    path = default_storage.save(media_path, ContentFile(b''))
    full_path = settings.MEDIA_ROOT + '/' + path
    report.to_csv(full_path)

    # initiate the download, user will stay on the same page
    with open(full_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=' + file_name
        response['Content-Type'] = 'application/vnd.ms-excel; charset=utf-16'
        return response
