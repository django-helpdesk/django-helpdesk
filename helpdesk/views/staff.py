"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/staff.py - The bulk of the application - provides most business logic and
                 renders all staff-facing views.
"""
from __future__ import unicode_literals
from datetime import datetime, timedelta

from django import VERSION as DJANGO_VERSION
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models.functions import Concat
from django.template.defaultfilters import date
from django.template.loader import render_to_string
from django.urls import reverse
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Value
from django.http import HttpResponseRedirect, Http404, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import make_aware
from django.utils.translation import ugettext as _
from django.utils import timezone

from django.utils import six
from django.views.decorators.http import require_POST
from helpdesk.filters import FeedbackSurveyFilter

from helpdesk.forms import (
    TicketForm, UserSettingsForm, EmailIgnoreForm, EditTicketForm, TicketCCForm,
    TicketCCEmailForm, TicketCCUserForm, EditFollowUpForm, TicketDependencyForm, InformationTicketForm,
    CreateFollowUpForm, MultipleTicketSelectForm
)
from helpdesk.decorators import staff_member_required, superuser_required
from helpdesk.lib import (
    send_templated_mail, apply_query, safe_template_context,
    process_attachments, queue_template_context, get_assignable_users,
)
from helpdesk.models import (
    Ticket, Queue, FollowUp, PreSetReply, Attachment, SavedSearch,
    IgnoreEmail, TicketCC, TicketDependency, TicketSpentTime, TicketCategory, TicketType, FeedbackSurvey,
)
from helpdesk import settings as helpdesk_settings

from base.decorators import ipexia_protected
from base.forms import SpentTimeForm
from base.models import Employee, Notification
from base.utils import handle_date_range_picker_filter, daterange
from config.settings.base import DATETIME_LOCAL_FORMAT
from sphinx.models import Customer, Site, CustomerProducts

User = get_user_model()


def _get_user_queues(user):
    """Return the list of Queues the user can access.

    :param user: The User (the class should have the has_perm method)
    :return: A Python list of Queues
    """
    all_queues = Queue.objects.all()
    limit_queues_by_user = \
        helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION \
        and not user.is_superuser
    if limit_queues_by_user:
        id_list = [q.pk for q in all_queues if user.has_perm(q.permission_name)]
        return all_queues.filter(pk__in=id_list)
    else:
        return all_queues


def _has_access_to_queue(user, queue):
    """Check if a certain user can access a certain queue.

    :param user: The User (the class should have the has_perm method)
    :param queue: The django-helpdesk Queue instance
    :return: True if the user has permission (either by default or explicitly), false otherwise
    """
    if user.is_superuser or not helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION:
        return True
    else:
        return user.has_perm(queue.permission_name)


def _is_my_ticket(user, ticket):
    """
    Check to see if the user has permission to access a ticket. If not then deny access.

    :param User user:
    :param Ticket ticket:
    :rtype: bool
    """
    if user.is_superuser or user.employee.is_ipexia_member \
            or ticket.customer_contact and ticket.customer_contact == user \
            or ticket.submitter_email and ticket.submitter_email == user.email \
            or ticket.customer and user.has_perm('view_customer', ticket.customer):
        return True
    else:
        return False


@staff_member_required
def dashboard(request):
    """
    A quick summary overview for users: A list of their own tickets, a table
    showing ticket counts by queue/status, and a list of unassigned tickets
    with options for them to 'Take' ownership of said tickets.
    """

    # user settings num tickets per page
    tickets_per_page = request.user.usersettings_helpdesk.settings.get('tickets_per_page') or 25

    # page vars for the three ticket tables
    user_tickets_page = request.GET.get(_('ut_page'), 1)
    user_tickets_closed_resolved_page = request.GET.get(_('utcr_page'), 1)
    all_tickets_reported_by_current_user_page = request.GET.get(_('atrbcu_page'), 1)

    # open & reopened tickets, assigned to current user
    tickets = Ticket.objects.select_related('queue').filter(
        assigned_to=request.user,
    ).exclude(
        status__in=[Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS],
    )

    # closed & resolved tickets, assigned to current user
    tickets_closed_resolved = Ticket.objects.select_related('queue').filter(
        assigned_to=request.user,
        status__in=[Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS])

    user_queues = _get_user_queues(request.user)

    unassigned_tickets = Ticket.objects.select_related('queue').filter(
        assigned_to__isnull=True,
        queue__in=user_queues
    ).exclude(
        status__in=[Ticket.CLOSED_STATUS, Ticket.DUPLICATE_STATUS],
    )

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

    queues = _get_user_queues(request.user).values_list('id', flat=True)

    from_clause = """FROM    helpdesk_ticket t,
                    helpdesk_queue q"""
    if queues:
        where_clause = """WHERE   q.id = t.queue_id AND
                        q.id IN (%s)""" % (",".join(("%d" % pk for pk in queues)))
    else:
        where_clause = """WHERE   q.id = t.queue_id"""

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
        'all_tickets_reported_by_current_user': all_tickets_reported_by_current_user,
        'basic_ticket_stats': basic_ticket_stats,
    })


@staff_member_required
def delete_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if not _has_access_to_queue(request.user, ticket.queue):
        raise PermissionDenied()
    if not _is_my_ticket(request.user, ticket):
        raise PermissionDenied()

    if request.method == 'GET':
        return render(request, 'helpdesk/delete_ticket.html', {
            'ticket': ticket,
        })
    else:
        ticket.delete()
        return HttpResponseRedirect(reverse('helpdesk:home'))


@staff_member_required
def followup_edit(request, ticket_id, followup_id):
    """Edit followup options with an ability to change the ticket."""
    followup = get_object_or_404(FollowUp, id=followup_id)
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if not _has_access_to_queue(request.user, ticket.queue):
        raise PermissionDenied()
    if not _is_my_ticket(request.user, ticket):
        raise PermissionDenied()

    form = EditFollowUpForm(request.POST or None, instance=followup)
    if form.is_valid():
        form.save()
        messages.success(request, 'La réponse a bien été mise à jour.')
        return redirect(ticket)

    return render(request, 'helpdesk/followup_edit.html', {
        'followup': followup,
        'ticket': ticket,
        'form': form,
    })


@staff_member_required
def followup_delete(request, ticket_id, followup_id):
    """followup delete for superuser"""

    ticket = get_object_or_404(Ticket, id=ticket_id)
    if not request.user.is_superuser:
        return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket.id]))

    followup = get_object_or_404(FollowUp, id=followup_id)
    followup.delete()
    return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket.id]))


@require_POST
@staff_member_required
def quick_update_ticket(request, ticket_id):
    """ Update ticket category, type or billing through AJAX """
    if not request.is_ajax():
        return Http404()
    ticket = get_object_or_404(Ticket, id=ticket_id)
    field = request.POST.get('field')
    if not field:
        return JsonResponse({'success': False, 'error': "Le champ du ticket n'est pas spécifié."})
    try:
        value = int(request.POST['value'])
    except KeyError:
        return JsonResponse({'success': False, 'error': "La valeur n'est pas spécifié."})
    except ValueError:
        return JsonResponse({'success': False, 'error': "Veuillez choisir une option dans la liste."})
    if not hasattr(ticket, field):
        return JsonResponse({'success': False, 'error': "Le champ %s n'existe pas sur le ticket."})

    setattr(ticket, field + ('_id' if field != 'billing' else ''), value)
    ticket.save(update_fields=[field])
    ticket.refresh_from_db()
    if field == 'type' and ticket.type.mandatory_facturation:
        return JsonResponse({'success': True, 'mandatory_facturation': True})
    return JsonResponse({'success': True})


@login_required
def view_ticket(request, ticket_id):
    ticket = get_object_or_404(
        Ticket.objects.prefetch_related(
            'followup_set__user', 'followup_set__ticketchange_set',
            'followup_set__attachment_set', 'ticketdependency__depends_on'
        ),
        id=ticket_id
    )
    if not _has_access_to_queue(request.user, ticket.queue):
        raise PermissionDenied('User has not access to the queue')
    if not _is_my_ticket(request.user, ticket):
        raise PermissionDenied('User has not access to ticket')

    # Try to save the quick comment if it is an AJAX POST request
    if request.user.is_staff and request.is_ajax() and request.method == 'POST':
        if request.POST.get('quickComment') is None:
            return JsonResponse({'success': False, 'error': 'Commentaire introuvable dans la requête'})

        ticket.quick_comment = request.POST.get('quickComment')
        try:
            ticket.save()
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
        return JsonResponse({'success': True})

    if 'take' in request.GET or ('close' in request.GET and ticket.status == Ticket.RESOLVED_STATUS):
        # Trick the update_ticket() view into thinking it's being called with a valid POST.
        request.POST = {
            'public': True,
            'title': ticket.title,
            'comment': '',
            'due_date': datetime.strftime(timezone.localtime(ticket.due_date),
                                          DATETIME_LOCAL_FORMAT) if ticket.due_date else None,
            'customer_contact': ticket.customer_contact.id if ticket.customer_contact else None,
            'customer': ticket.customer.id if ticket.customer else None,
            'site': ticket.site.id if ticket.site else None,
            'customer_product': ticket.customer_product.id if ticket.customer_product else None,
        }
        if 'take' in request.GET:
            # Allow the user to assign the ticket to themselves whilst viewing it
            request.POST['owner'] = request.user.id
        elif 'close' in request.GET:
            if request.user.is_staff:
                if ticket.assigned_to:
                    request.POST['owner'] = ticket.assigned_to.id
                request.POST['new_status'] = Ticket.CLOSED_STATUS
                request.POST['comment'] = _('Accepted resolution and closed ticket')
                # Let user to close ticket without notifying customer
                if 'private' in request.GET:
                    request.POST['public'] = False
                    request.POST['comment'] = 'Solution acceptée et ticket fermé sans notification au client'
            else:
                ticket.status = Ticket.CLOSED_STATUS
                ticket.save()
                ticket.followup_set.create(
                    title=ticket.get_status_display(),
                    comment='Solution acceptée par le client.',
                    public=True,
                    new_status=Ticket.CLOSED_STATUS
                )
                context = safe_template_context(ticket)
                # Send mail to assigned user
                if ticket.assigned_to:
                    send_templated_mail(
                        'closed_owner',
                        context,
                        recipients=ticket.assigned_to.email,
                        sender=ticket.queue.from_address,
                        fail_silently=True
                    )
                    # Send Phoenix notification
                    Notification.objects.create(
                        module=Notification.TICKET,
                        message="Le ticket %s vient d'être fermé par %s" % (ticket, request.user),
                        link_redirect=ticket.get_absolute_url(),
                        user_list=[ticket.assigned_to]
                    )
                messages.success(request, 'Le ticket a bien été fermé.')
                # FIXME Ticket CC and queue CC don't receive mails
                return redirect('helpdesk:feedback_survey', ticket.id)

        return update_ticket(request, ticket_id)

    if 'subscribe' in request.GET:
        # Allow the user to subscribe him/herself to the ticket whilst viewing it.
        ticket_cc, show_subscribe = \
            return_ticketccstring_and_show_subscribe(request.user, ticket)
        if show_subscribe:
            subscribe_staff_member_to_ticket(ticket, request.user)
            return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket.id]))

    if helpdesk_settings.HELPDESK_STAFF_ONLY_TICKET_OWNERS:
        users = User.objects.filter(is_active=True, is_staff=True).order_by(User.USERNAME_FIELD)
    else:
        users = User.objects.filter(is_active=True).order_by(User.USERNAME_FIELD)

    followup_form = CreateFollowUpForm(request.POST or None)

    if request.user.employee.is_ipexia_member:
        form = TicketForm(
            initial={
                'due_date': ticket.due_date,
                'customer': ticket.customer,
                'customer_contact': ticket.customer_contact,
                'site': ticket.site,
                'customer_product': ticket.customer_product,
                'quick_comment': ticket.quick_comment,
            },
            user=request.user,
            edit_contextual_fields=True
        )

        information_form = InformationTicketForm(instance=ticket)

        # Filter the ongoing spent_time on this step
        spent_times = ticket.spent_times.filter(status=TicketSpentTime.ONGOING)
    else:
        # Non ipexia users don't need these
        form = None
        information_form = None
        spent_times = None
        # Check if follow up is valid, only if ticket is not too old
        if followup_form.is_valid() and not ticket.is_closed_and_too_old():
            follow_up = followup_form.save(commit=False)
            follow_up.ticket = ticket
            follow_up.user = request.user
            follow_up.title = 'Réponse client'
            follow_up.public = True
            # TODO handle status change ?
            follow_up.save()
            messages.success(request, 'Votre réponse a bien été envoyé.')
            files = process_attachments(follow_up, request.FILES.getlist('attachment'))
            if files:
                messages.info(request, 'Les fichiers joints ont également été associés à la réponse.')
            # Send mail to assigned user
            if ticket.assigned_to:
                context = safe_template_context(ticket)
                context['ticket']['comment'] = follow_up.comment
                send_templated_mail(
                    'updated_owner',
                    context,
                    recipients=ticket.assigned_to.email,
                    sender=ticket.queue.from_address,
                    fail_silently=True,
                    files=files
                )
                # Send Phoenix notification
                Notification.objects.create(
                    module=Notification.TICKET,
                    message='Une nouvelle réponse a été ajouté au ticket %s par %s' % (ticket, request.user),
                    link_redirect=ticket.get_absolute_url(),
                    user_list=[ticket.assigned_to]
                )
            # FIXME Ticket CC and queue CC don't receive emails
            return redirect(ticket)

    ticketcc_string, show_subscribe = \
        return_ticketccstring_and_show_subscribe(request.user, ticket)

    return render(request, 'helpdesk/ticket.html', {
        'ticket': ticket,
        'form': form,
        'followup_form': followup_form,
        'information_form': information_form,
        'active_users': users,
        'priorities': Ticket.PRIORITY_CHOICES,
        'preset_replies': PreSetReply.objects.filter(
            Q(queues=ticket.queue) | Q(queues__isnull=True)),
        'ticketcc_string': ticketcc_string,
        'SHOW_SUBSCRIBE': show_subscribe,
        'spent_times': spent_times
    })


@staff_member_required
def ticket_spent_times(request, ticket_id, spent_time_id=None):
    """ List of the spent times of the ticket """
    ticket = get_object_or_404(Ticket, id=ticket_id)
    spent_times = ticket.spent_times.select_related('employee__user')

    edit_spent_time = None
    if spent_time_id:
        edit_spent_time = get_object_or_404(spent_times, id=spent_time_id)

    form = SpentTimeForm(request.POST or None, instance=edit_spent_time, initial={
        'status': edit_spent_time.status if edit_spent_time else TicketSpentTime.FINISHED,
        'end_date': edit_spent_time.end_date if edit_spent_time else timezone.now()
    })
    if form.is_valid():
        spent_time = form.save(commit=False)
        spent_time.ticket = ticket
        spent_time.employee = request.user.employee
        spent_time.save()

        # If the end_date has been filled, set the duration
        if form.cleaned_data['end_date']:
            spent_time.end_track(form.cleaned_data['end_date'], with_error=spent_time.status == TicketSpentTime.ERROR)
        else:
            # Remove duration
            spent_time.duration = None
            spent_time.save(update_fields=['duration'])

        if edit_spent_time:
            text = 'modifié'
        else:
            text = 'ajouté'
        messages.success(request, "L'enregistrement de temps a bien été %s au ticket." % text)

        return redirect('helpdesk:ticket_spent_times', ticket_id)

    return render(request, 'helpdesk/ticket_spent_times.html', {
        'ticket': ticket,
        'spent_times': spent_times,
        'edit_spent_time': edit_spent_time,
        'form': form
    })


@staff_member_required
def start_spent_time(request, ticket_id, employee_id):
    """ Create a new OrderProductStepSpentTime for the user on the order product step """
    ticket = get_object_or_404(Ticket, id=ticket_id)
    employee = get_object_or_404(Employee, id=employee_id)

    # Check first if the user has no ongoing spent time
    if not employee.spent_times.filter(status=TicketSpentTime.ONGOING).exists():
        spent_time = TicketSpentTime.objects.create(ticket=ticket, employee=employee)
    else:
        return JsonResponse({'success': False, 'error': 'Un chrono a déjà été lancé !'})

    return JsonResponse({
        'success': True,
        'spent_time_id': spent_time.id,
        'ongoing_spent_time_top_navigation': render_to_string(
            'base/components/spent_time/ongoing_spent_time_top_navigation.html', {
            'ongoing_spent_time': spent_time
        }),
        'ongoing_spent_time_actions': render_to_string(
            'base/components/spent_time/ongoing_spent_time_actions.html', {
            'ongoing_spent_time': spent_time
        }),
        'table': render_to_string('base/components/spent_time/spent_times_table.html', {
            'request': request,
            'spent_times': spent_time.ticket.spent_times.select_related('employee__user')
        })
    })


def return_ticketccstring_and_show_subscribe(user, ticket):
    """used in view_ticket() and followup_edit()"""
    # create the ticketcc_string and check whether current user is already
    # subscribed
    username = user.get_username().upper()
    useremail = user.email.upper()
    user_full_name = str(user).upper()
    strings_to_check = list()
    strings_to_check.append(username)
    strings_to_check.append(useremail)
    strings_to_check.append(user_full_name)

    ticketcc_string = ''
    all_ticketcc = ticket.ticketcc_set.all()
    counter_all_ticketcc = len(all_ticketcc) - 1
    show_subscribe = True
    for i, ticketcc in enumerate(all_ticketcc):
        ticketcc_this_entry = str(ticketcc.display)
        ticketcc_string += ticketcc_this_entry
        if i < counter_all_ticketcc:
            ticketcc_string += ', '
        if ticketcc_this_entry.upper() in strings_to_check:
            show_subscribe = False

    # check whether current user is a submitter or assigned to ticket
    assignedto_username = str(ticket.assigned_to).upper()
    strings_to_check = list()
    if ticket.submitter_email is not None:
        submitter_email = ticket.submitter_email.upper()
        strings_to_check.append(submitter_email)
    strings_to_check.append(assignedto_username)
    if username in strings_to_check or useremail in strings_to_check or user_full_name in strings_to_check:
        show_subscribe = False

    return ticketcc_string, show_subscribe


def subscribe_staff_member_to_ticket(ticket, user):
    """used in view_ticket() and update_ticket()"""
    if not ticket.ticketcc_set.filter(user=user).exists():
        ticketcc = TicketCC(
            ticket=ticket,
            user=user,
            can_view=True,
            can_update=True,
        )
        ticketcc.save()


@staff_member_required
def choose_customer_for_ticket(request, ticket_id, customer_id):
    """ Link customer to the ticket given in parameter """
    ticket = get_object_or_404(Ticket, id=ticket_id)
    customer = get_object_or_404(Customer, id=customer_id)

    ticket.customer = customer
    ticket.save(update_fields=['customer'])
    messages.success(request, 'Le client {} est désormais associé au ticket {}'.format(customer, ticket.ticket_for_url))

    return redirect(ticket)


@login_required
@ipexia_protected()
def update_ticket(request, ticket_id, public=False):
    if not (public or (
            request.user.is_authenticated and
            request.user.is_active and (
                request.user.is_staff or
                helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE))):
        return HttpResponseRedirect('%s?next=%s' %
                                    (reverse('helpdesk:login'), request.path))

    ticket = get_object_or_404(Ticket, id=ticket_id)

    comment = request.POST.get('comment', '')
    new_status = int(request.POST.get('new_status', ticket.status))
    title = request.POST.get('title', '')
    public = request.POST.get('public', False)
    owner = int(request.POST.get('owner', -1))
    priority = int(request.POST.get('priority', ticket.priority))
    due_date = request.POST.get('due_date')
    customer_contact_id = int(request.POST.get('customer_contact')) if request.POST.get('customer_contact') else None
    customer_id = int(request.POST.get('customer')) if request.POST.get('customer') else None
    site_id = int(request.POST.get('site')) if request.POST.get('site') else None
    customer_product_id = int(request.POST.get('customer_product', None)) if request.POST.get('customer_product') else None

    if due_date:
        due_date = make_aware(datetime.strptime(due_date, DATETIME_LOCAL_FORMAT))
    else:
        due_date = None

    no_changes = all([
        not request.FILES,
        not comment,
        new_status == ticket.status,
        title == ticket.title,
        priority == int(ticket.priority),
        due_date == ticket.due_date,
        customer_contact_id == (ticket.customer_contact.id if ticket.customer_contact else None),
        customer_id == (ticket.customer.id if ticket.customer else None),
        site_id == (ticket.site.id if ticket.site else None),
        customer_product_id == (ticket.customer_product.id if ticket.customer_product else None),
        (owner == -1) or (not owner and not ticket.assigned_to) or
        (owner and User.objects.get(id=owner) == ticket.assigned_to),
    ])
    if no_changes:
        messages.info(request, "Aucune modification n'a été apportée.")
        return return_to_ticket(request.user, helpdesk_settings, ticket)

    # We need to allow the 'ticket' and 'queue' contexts to be applied to the
    # comment.
    context = safe_template_context(ticket)

    from django.template import engines
    template_func = engines['django'].from_string
    # this prevents system from trying to render any template tags
    # broken into two stages to prevent changes from first replace being themselves
    # changed by the second replace due to conflicting syntax
    comment = comment.replace('{%', 'X-HELPDESK-COMMENT-VERBATIM').replace('%}', 'X-HELPDESK-COMMENT-ENDVERBATIM')
    comment = comment.replace('X-HELPDESK-COMMENT-VERBATIM', '{% verbatim %}{%').replace('X-HELPDESK-COMMENT-ENDVERBATIM', '%}{% endverbatim %}')
    # render the neutralized template
    comment = template_func(comment).render(context)

    if owner is -1 and ticket.assigned_to:
        owner = ticket.assigned_to.id

    f = FollowUp(ticket=ticket, user=request.user, date=timezone.now(), comment=comment, public=public)

    # Append signature at the bottom of the followup comment if a comment was made and the followup is public
    if comment and public:
        f.append_signature(request.user)

    reassigned = False
    old_owner = ticket.assigned_to

    # Build followup title
    if owner is not -1:
        if owner != 0 and ((ticket.assigned_to and owner != ticket.assigned_to.id) or not ticket.assigned_to):
            new_user = User.objects.get(id=owner)
            # TODO fix translate
            f.title = 'Assigné à %s' % new_user
            ticket.assigned_to = new_user
            reassigned = True
        # user changed owner to 'unassign'
        elif owner == 0 and ticket.assigned_to is not None:
            f.title = _('Unassigned')
            ticket.assigned_to = None

    old_status_str = ticket.get_status_display()
    old_status = ticket.status
    if new_status != ticket.status:
        ticket.status = new_status
        ticket.save()
        messages.info(request, 'Le ticket est désormais dans le statut %s' % ticket.get_status_display())
        f.new_status = new_status
        if f.title:
            # TODO translate
            f.title += ' et %s' % ticket.get_status_display()
        else:
            f.title = '%s' % ticket.get_status_display()

    if not f.title:
        if f.comment:
            f.title = _('Comment')
        else:
            f.title = _('Updated')

    f.save()

    files = process_attachments(f, request.FILES.getlist('attachment'))

    # Add Ticket Changes
    if title and title != ticket.title:
        f.ticketchange_set.create(
            field=_('Title'),
            old_value=ticket.title,
            new_value=title,
        )
        ticket.title = title

    if new_status != old_status:
        f.ticketchange_set.create(
            field=_('Status'),
            old_value=old_status_str,
            new_value=ticket.get_status_display(),
        )

    if ticket.assigned_to != old_owner:
        f.ticketchange_set.create(
            field=_('Owner'),
            old_value=old_owner if old_owner else _('Unassigned'),
            new_value=ticket.assigned_to if ticket.assigned_to else _('Unassigned'),
        )

    if priority != ticket.priority:
        f.ticketchange_set.create(
            field=_('Priority'),
            old_value=ticket.priority,
            new_value=priority,
        )
        ticket.priority = priority

    if due_date != ticket.due_date:
        f.ticketchange_set.create(
            field=_('Due on'),
            old_value=date(timezone.localtime(ticket.due_date), 'DATETIME_FORMAT') if ticket.due_date else 'Non définie',
            new_value=date(due_date, 'DATETIME_FORMAT') if due_date else 'Non définie',
        )
        ticket.due_date = due_date

    if customer_contact_id != (ticket.customer_contact.id if ticket.customer_contact else None):
        try:
            customer_contact = User.objects.get(id=customer_contact_id)
        except User.DoesNotExist:
            customer_contact = None
        f.ticketchange_set.create(
            field='Contact client',
            old_value=str(ticket.customer_contact) if ticket.customer_contact else _('Unassigned'),
            new_value=str(customer_contact) if customer_contact else _('Unassigned'),
        )
        ticket.customer_contact = customer_contact

    if customer_id != (ticket.customer.id if ticket.customer else None):
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            customer = None
        f.ticketchange_set.create(
            field='Client',
            old_value=str(ticket.customer) if ticket.customer else _('Unassigned'),
            new_value=str(customer) if customer else _('Unassigned'),
        )
        ticket.customer = customer

    if site_id != (ticket.site.id if ticket.site else None):
        try:
            site = Site.objects.get(id=site_id)
        except Site.DoesNotExist:
            site = None
        f.ticketchange_set.create(
            field='Site',
            old_value=str(ticket.site) if ticket.site else _('Unassigned'),
            new_value=str(site) if site else _('Unassigned'),
        )
        ticket.site = site

    if customer_product_id != (ticket.customer_product.id if ticket.customer_product else None):
        try:
            customer_product = CustomerProducts.objects.get(id=customer_product_id)
        except CustomerProducts.DoesNotExist:
            customer_product = None
        f.ticketchange_set.create(
            field='Produit client',
            old_value=str(ticket.customer_product) if ticket.customer_product else _('Unassigned'),
            new_value=str(customer_product) if customer_product else _('Unassigned'),
        )
        ticket.customer_product = customer_product

    if new_status in (Ticket.RESOLVED_STATUS, Ticket.CLOSED_STATUS):
        if new_status == Ticket.RESOLVED_STATUS or ticket.resolution is None:
            ticket.resolution = comment

    messages_sent_to = []

    # ticket might have changed above, so we re-instantiate context with the
    # (possibly) updated ticket.
    context = safe_template_context(ticket)
    context['ticket']['comment'] = f.comment

    if public and (f.comment or (f.new_status in (Ticket.RESOLVED_STATUS, Ticket.CLOSED_STATUS))):
        if f.new_status == Ticket.RESOLVED_STATUS:
            template = 'resolved_'
        elif f.new_status == Ticket.CLOSED_STATUS:
            template = 'closed_'
        else:
            template = 'updated_'

        template_suffix = 'submitter'

        if ticket.get_submitter_emails():
            send_templated_mail(
                template + template_suffix,
                context,
                recipients=ticket.get_submitter_emails(),
                sender=ticket.queue.from_address,
                fail_silently=True,
                files=files,
            )
            messages_sent_to += ticket.get_submitter_emails()

        template_suffix = 'cc'

        for cc in ticket.ticketcc_set.all():
            if cc.email_address not in messages_sent_to:
                send_templated_mail(
                    template + template_suffix,
                    context,
                    recipients=cc.email_address,
                    sender=ticket.queue.from_address,
                    fail_silently=True,
                    files=files,
                )
                messages_sent_to.append(cc.email_address)

    if ticket.assigned_to and \
            request.user != ticket.assigned_to and \
            ticket.assigned_to.email and \
            ticket.assigned_to.email not in messages_sent_to:
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

        if (not reassigned or
                (reassigned and
                    ticket.assigned_to.usersettings_helpdesk.settings.get(
                        'email_on_ticket_assign', False))) or \
            (not reassigned and
                ticket.assigned_to.usersettings_helpdesk.settings.get(
                    'email_on_ticket_change', False)):
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

    # auto subscribe user if enabled
    if helpdesk_settings.HELPDESK_AUTO_SUBSCRIBE_ON_TICKET_RESPONSE and request.user.is_authenticated:
        ticketcc_string, SHOW_SUBSCRIBE = return_ticketccstring_and_show_subscribe(request.user, ticket)
        if SHOW_SUBSCRIBE:
            subscribe_staff_member_to_ticket(ticket, request.user)

    return return_to_ticket(request.user, helpdesk_settings, ticket)


def return_to_ticket(user, helpdesk_settings, ticket):
    """Helper function for update_ticket"""

    if user.is_staff or helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE:
        return HttpResponseRedirect(ticket.get_absolute_url())
    else:
        return HttpResponseRedirect(ticket.ticket_url)


@staff_member_required
def mass_update(request):
    tickets = request.POST.getlist('ticket_id')
    action = request.POST.get('action', None)
    if not (tickets and action):
        messages.warning(request, 'Veuillez sélectionner au minimum 1 ticket et choisir une action à effectuer.')
        return redirect('helpdesk:list')

    if action.startswith('assign_'):
        parts = action.split('_')
        user = User.objects.get(id=parts[1])
        action = 'assign'
    elif action == 'take':
        user = request.user
        action = 'assign'
    elif action == 'delete':
        tickets = Ticket.objects.filter(id__in=tickets)
        tickets_count = len(tickets)
        tickets.delete()
        if tickets_count == 1:
            msg = 'Un ticket a été supprimé.'
        else:
            msg = '%d tickets ont été supprimés' % tickets_count
        messages.success(request, msg)
        return redirect('helpdesk:list')
    elif action == 'fusion':
        if len(tickets) < 2:
            messages.warning(request, 'Veuillez sélectionner au minimum 2 tickets pour pouvoir les fusionner.')
        elif len(tickets) > 4:
            messages.warning(request, "Oulà, ça risque d'être compliqué pour moi plus de 4 tickets...")
        else:
            return redirect(
                reverse('helpdesk:fusion') + '?' + '&'.join(['tickets=%s' % ticket_id for ticket_id in tickets])
            )
        return redirect('helpdesk:list')

    for t in Ticket.objects.filter(id__in=tickets):
        if not _has_access_to_queue(request.user, t.queue):
            continue

        if action == 'assign' and t.assigned_to != user:
            t.assigned_to = user
            t.save()
            f = FollowUp(ticket=t,
                         date=timezone.now(),
                         # TODO fix translate
                         title="Assigné à %s dans l'édition en masse" % user,
                         public=True,
                         user=request.user)
            f.save()
        elif action == 'unassign' and t.assigned_to is not None:
            t.assigned_to = None
            t.save()
            f = FollowUp(ticket=t,
                         date=timezone.now(),
                         title=_('Unassigned in bulk update'),
                         public=True,
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
            # Send email to Submitter, Owner, Queue CC
            context = safe_template_context(t)
            context['ticket']['resolution'] = t.resolution

            messages_sent_to = []

            if t.get_submitter_emails():
                send_templated_mail(
                    'closed_submitter',
                    context,
                    recipients=t.get_submitter_emails(),
                    sender=t.queue.from_address,
                    fail_silently=True,
                )
                messages_sent_to += t.get_submitter_emails()

            for cc in t.ticketcc_set.all():
                if cc.email_address not in messages_sent_to:
                    send_templated_mail(
                        'closed_cc',
                        context,
                        recipients=cc.email_address,
                        sender=t.queue.from_address,
                        fail_silently=True,
                    )
                    messages_sent_to.append(cc.email_address)

            if t.assigned_to and \
                    request.user != t.assigned_to and \
                    t.assigned_to.email and \
                    t.assigned_to.email not in messages_sent_to:
                send_templated_mail(
                    'closed_owner',
                    context,
                    recipients=t.assigned_to.email,
                    sender=t.queue.from_address,
                    fail_silently=True,
                )
                messages_sent_to.append(t.assigned_to.email)

            if t.queue.updated_ticket_cc and \
                    t.queue.updated_ticket_cc not in messages_sent_to:
                send_templated_mail(
                    'closed_cc',
                    context,
                    recipients=t.queue.updated_ticket_cc,
                    sender=t.queue.from_address,
                    fail_silently=True,
                )

    return redirect('helpdesk:list')


ticket_attributes = (
    ('created', 'Date de création'),
    ('due_date', "Date d'échéance"),
    ('get_status_display', 'Statut'),
    ('submitter_email', 'Email émetteur'),
    ('customer_contact', 'Utilisateur Phoenix'),
    ('contact_phone_number', 'Téléphone de contact'),
    ('customer', 'Client'),
    ('site', 'Site'),
    ('customer_product', 'Produit client'),
    ('link_open', "Lien d'ouverture ticket"),
    ('assigned_to', "Technien affecté"),
    ('category', 'Catégorie'),
    ('type', 'Type'),
    ('get_billing_display', 'Facturation'),
    ('get_priority_display', 'Priorité'),
    ('quick_comment', 'Commentaire rapide'),
    ('description', 'Description'),
    ('resolution', 'Solution'),
)


@staff_member_required
def fusion_tickets(request):
    ticket_select_form = MultipleTicketSelectForm(request.GET or None)
    tickets = None
    if ticket_select_form.is_valid():
        tickets = ticket_select_form.cleaned_data.get('tickets')

        if request.method == 'POST':
            try:
                chosen_ticket = tickets.get(id=request.POST.get('chosen_ticket'))
            except Ticket.DoesNotExist:
                messages.error(request, 'Veuillez sélectionner un ticket dans lequel sera effectuée la fusion.')
            else:
                for attr, _ in ticket_attributes:
                    id_for_attr = request.POST.get(attr)
                    if id_for_attr != chosen_ticket.id:
                        try:
                            selected_ticket = tickets.get(id=id_for_attr)
                        except Ticket.DoesNotExist:
                            pass
                        else:
                            # Check if attr is a get_FIELD_display
                            if attr.startswith('get_') and attr.endswith('_display'):
                                # Keep only the FIELD part
                                attr = attr[4:-8]
                            value = getattr(selected_ticket, attr)
                            setattr(chosen_ticket, attr, value)
                # Save changes
                chosen_ticket.save()

                for ticket in tickets.exclude(id=chosen_ticket.id):
                    ticket.merged_to = chosen_ticket
                    ticket.status = Ticket.DUPLICATE_STATUS
                    # Override values from chosen ticket
                    ticket.assigned_to = ticket.merged_to.assigned_to
                    ticket.category = ticket.merged_to.category
                    ticket.type = ticket.merged_to.type
                    ticket.billing = ticket.merged_to.billing
                    ticket.customer = ticket.merged_to.customer
                    ticket.site = ticket.merged_to.site
                    ticket.customer_product = ticket.merged_to.customer_product
                    ticket.save()

                    # Send mail to submitter email
                    context = safe_template_context(ticket)
                    if ticket.get_submitter_emails():
                        send_templated_mail(
                            'merged',
                            context,
                            recipients=ticket.get_submitter_emails(),
                            sender=ticket.queue.from_address,
                            fail_silently=True
                        )

                    # Move all followups and update their title to know they come from another ticket
                    ticket.followup_set.update(
                        ticket=chosen_ticket,
                        # Next might exceed maximum 200 characters limit
                        title=Concat(Value('[Fusion de #%d] ' % ticket.id), 'title')
                    )

                    # Add submitter_email, assigned_to email and ticketcc to chosen ticket if necessary
                    chosen_ticket.add_email_to_ticketcc_if_not_in(email=ticket.submitter_email)
                    if ticket.customer_contact and ticket.customer_contact.email:
                        chosen_ticket.add_email_to_ticketcc_if_not_in(email=ticket.customer_contact.email)
                    if ticket.assigned_to and ticket.assigned_to.email:
                        chosen_ticket.add_email_to_ticketcc_if_not_in(email=ticket.assigned_to.email)
                    for ticketcc in ticket.ticketcc_set.all():
                        chosen_ticket.add_email_to_ticketcc_if_not_in(ticketcc=ticketcc)
                messages.success(request, 'Les tickets ont bien été fusionnées dans le ticket %s' % chosen_ticket)
                return redirect(chosen_ticket)

    return render(request, 'helpdesk/ticket_merge.html', {
        'tickets': tickets,
        'ticket_attributes': ticket_attributes,
        'ticket_select_form': ticket_select_form
    })


@staff_member_required
def ticket_list(request):
    context = {}

    user_queues = _get_user_queues(request.user)
    # Prefilter the allowed tickets
    base_tickets = Ticket.objects.filter(queue__in=user_queues)

    # Prepare a default query params
    default_query_params = {
        'filtering': {'status__in': [1, 2, 3]},
        'sorting': 'modified',
        'sortreverse': True,
        'search_string': None,
        'created_relative': {
            'days': None,
            'direction': 'before'
        }
    }

    # Query_params will hold a dictionary of parameters relating to
    # a query, to be saved if needed:
    query_params = default_query_params

    from_saved_query = False

    # If the user is coming from the header/navigation search box, lets' first
    # look at their query to see if they have entered a valid ticket number. If
    # they have, just redirect to that ticket number. Otherwise, we treat it as
    # a keyword search.

    if request.GET.get('search_type') == 'header':
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
                ticket = base_tickets.get(**filter)
                return HttpResponseRedirect(ticket.staff_url)
            except Ticket.DoesNotExist:
                # Go on to standard keyword searching
                pass

    saved_query = None
    if request.GET.get('saved_query'):
        from_saved_query = True
        try:
            saved_query = SavedSearch.objects.get(pk=request.GET.get('saved_query'))
        except SavedSearch.DoesNotExist:
            return HttpResponseRedirect(reverse('helpdesk:list'))
        if not (saved_query.shared or saved_query.user == request.user):
            return HttpResponseRedirect(reverse('helpdesk:list'))

        import json
        from helpdesk.lib import b64decode
        try:
            query_params = json.loads(b64decode(str(saved_query.query).lstrip("b\\'")).decode())
        except ValueError:
            # Query deserialization failed. (E.g. was a pickled query)
            return HttpResponseRedirect(reverse('helpdesk:list'))

    elif not ('queues' in request.GET or
              'assigned_to' in request.GET or
              'status' in request.GET or
              'q' in request.GET or
              'sort' in request.GET or
              'sortreverse' in request.GET):

        # Fall-back if no querying is being done, force the list to only
        # show open/reopened/resolved (not closed) cases sorted by creation
        # date.

        query_params = default_query_params
    else:
        def add_to_query_params(query_params_dict, name, name_plural=None, use_id=True):
            """
            :param dict query_params_dict: dictionnary with all params for the query to filter tickets
            :param str name: name of the field
            :param str name_plural: name of the field in plural
            """
            object_ids = request.GET.getlist(name_plural if name_plural else name)
            if object_ids:
                try:
                    key = '%s__id__in' if use_id else '%s__in'
                    query_params_dict['filtering'][key % name] = [int(obj) for obj in object_ids]
                except ValueError:
                    pass
            return query_params_dict

        query_params = add_to_query_params(query_params, 'queue', 'queues')
        query_params = add_to_query_params(query_params, 'customer', 'customers')
        query_params = add_to_query_params(query_params, 'category', 'categories')
        query_params = add_to_query_params(query_params, 'type', 'types')
        query_params = add_to_query_params(query_params, 'billing', 'billings', use_id=False)
        query_params = add_to_query_params(query_params, 'assigned_to')
        query_params = add_to_query_params(query_params, 'status', use_id=False)

        date_from = request.GET.get('date_from')
        if date_from:
            query_params['filtering']['created__date__gte'] = date_from

        date_to = request.GET.get('date_to')
        if date_to:
            query_params['filtering']['created__date__lte'] = date_to

        created_relative_days = request.GET.get('created_relative_days')
        if created_relative_days:
            try:
                created_relative_days = int(created_relative_days)
            except ValueError:
                pass
            else:
                query_params['created_relative']['days'] = created_relative_days
        query_params['created_relative']['direction'] = request.GET.get('direction', 'before')

        # KEYWORD SEARCHING
        q = request.GET.get('q')

        if q:
            context = dict(context, query=q)
            query_params['search_string'] = q

        # SORTING
        sortreverse = request.GET.get('sortreverse', False)
        query_params['sortreverse'] = sortreverse

        sort = request.GET.get('sort')
        if sort not in ('status', 'assigned_to', 'created', 'modified', 'title', 'queue', 'priority'):
            # Fallback to sort by created in reverse
            sort = 'modified'
            query_params['sortreverse'] = True
        query_params['sorting'] = sort

    tickets = base_tickets.select_related(
        'queue', 'category', 'type', 'customer_contact', 'customer__group', 'assigned_to'
    )

    try:
        ticket_qs = apply_query(tickets, query_params)
    except ValidationError:
        messages.error(request, "Une erreur s'est produite pendant le requête de filtre.")
        # invalid parameters in query, return default query
        query_params = default_query_params
        ticket_qs = apply_query(tickets, query_params)

    search_message = ''
    if 'query' in context and settings.DATABASES['default']['ENGINE'].endswith('sqlite'):
        search_message = _(
            '<p><strong>Note:</strong> Your keyword search is case sensitive '
            'because of your database. This means the search will <strong>not</strong> '
            'be accurate. By switching to a different database system you will gain '
            'better searching! For more information, read the '
            '<a href="http://docs.djangoproject.com/en/dev/ref/databases/#sqlite-string-matching">'
            'Django Documentation on string matching in SQLite</a>.')

    import json
    from helpdesk.lib import b64encode
    urlsafe_query = b64encode(json.dumps(query_params).encode('UTF-8'))

    user_saved_queries = SavedSearch.objects.select_related('user').filter(Q(user=request.user) | Q(shared__exact=True))

    return render(request, 'helpdesk/ticket_list.html', dict(
        context,
        tickets=ticket_qs,
        default_tickets_per_page=request.user.usersettings_helpdesk.settings.get('tickets_per_page') or 25,
        user_choices=get_assignable_users(),
        queue_choices=user_queues,
        customer_choices=Customer.objects.select_related('group'),
        category_choices=TicketCategory.objects.all(),
        type_choices=TicketType.objects.all(),
        billing_choices=Ticket.BILLINGS,
        status_choices=Ticket.STATUS_CHOICES,
        urlsafe_query=urlsafe_query,
        user_saved_queries=user_saved_queries,
        query_params=query_params,
        from_saved_query=from_saved_query,
        saved_query=saved_query,
        search_message=search_message
    ))


@staff_member_required
def edit_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if not _has_access_to_queue(request.user, ticket.queue):
        raise PermissionDenied()
    if not _is_my_ticket(request.user, ticket):
        raise PermissionDenied()

    form = EditTicketForm(request.POST or None, instance=ticket)
    if form.is_valid():
        ticket = form.save()
        return redirect(ticket)

    return render(request, 'helpdesk/edit_ticket.html', {'form': form})


@login_required
def create_ticket(request):
    if request.method == 'POST':
        # Add prefix if form has been submitted through the modal (and so has the ticket prefix)
        form = TicketForm(
            data=request.POST,
            files=request.FILES,
            prefix='ticket' if 'ticket-title' in request.POST else None,
            user=request.user
        )
        if form.is_valid():
            ticket = form.save(user=request.user)
            # Check if user wants to update his phone number
            if form.cleaned_data.get('update_phone_number'):
                # Update phone number if it has been changed
                contact_phone_number = form.cleaned_data.get('contact_phone_number')
                customer_contact = form.cleaned_data.get('customer_contact')
                if customer_contact and contact_phone_number is not None \
                        and customer_contact.employee.phone_number != contact_phone_number:
                    customer_contact.employee.phone_number = contact_phone_number
                    customer_contact.employee.save(update_fields=['phone_number'])
                    messages.info(request, 'Le numéro de téléphone de contact a bien été mis à jour.')
            # Send a notification if ticket has been added by a customer
            if not request.user.employee.is_ipexia_member:
                messages.success(request, 'Votre ticket a bien été créé !')
                # Send notification to technical service
                Notification.objects.create_for_technical_service(
                    message="Un nouveau ticket vient d'être ouvert sur Phoenix : %s" % ticket,
                    module=Notification.TICKET,
                    link_redirect=ticket.get_absolute_url()
                )
            else:
                messages.success(request, 'Le ticket a bien été créé.')
            if _has_access_to_queue(request.user, ticket.queue):
                return redirect(ticket)
            else:
                return redirect('helpdesk:dashboard')
    else:
        initial_data = {}
        if 'queue' in request.GET:
            initial_data['queue'] = request.GET['queue']

        form = TicketForm(initial=initial_data, user=request.user)

    return render(request, 'helpdesk/create_ticket.html', {'form': form})


@staff_member_required
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


@staff_member_required
def hold_ticket(request, ticket_id, unhold=False):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if not _has_access_to_queue(request.user, ticket.queue):
        raise PermissionDenied()
    if not _is_my_ticket(request.user, ticket):
        raise PermissionDenied()

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


@staff_member_required
def unhold_ticket(request, ticket_id):
    return hold_ticket(request, ticket_id, unhold=True)


@staff_member_required
def rss_list(request):
    return render(request, 'helpdesk/rss_list.html', {'queues': Queue.objects.all()})


#
USER_PRIORITY = 'userpriority'
USER_QUEUE = 'userqueue'
USER_STATUS = 'userstatus'
USER_CATEGORY = 'usercategory'
USER_TYPE = 'usertype'
USER_BILLING = 'userbilling'
USER_MONTH = 'usermonth'
QUEUE_PRIORITY = 'queuepriority'
QUEUE_STATUS = 'queuestatus'
QUEUE_CATEGORY = 'queuecategory'
QUEUE_TYPE = 'queuetype'
QUEUE_BILLING = 'queuebilling'
QUEUE_MONTH = 'queuemonth'
DAYS_UNTIL_TICKET_CLOSED_BY_MONTH = 'daysuntilticketclosedbymonth'

reports = {
    USER_PRIORITY: {
        'title': _('User by Priority'),
        'title_index': _('by Priority'),
        'col1_heading': _('User'),
        'chart_type': 'bar'
    },
    USER_QUEUE: {
        'title': _('User by Queue'),
        'title_index': _('by Queue'),
        'col1_heading': _('User'),
        'chart_type': 'bar'
    },
    USER_STATUS: {
        'title': _('User by Status'),
        'title_index': _('by Status'),
        'col1_heading': _('User'),
        'chart_type': 'bar'
    },
    USER_CATEGORY: {
        'title': 'Utilisateur par Catégorie',
        'title_index': 'par Catégorie',
        'col1_heading': _('User'),
        'chart_type': 'bar'
    },
    USER_TYPE: {
        'title': 'Utilisateur par Type',
        'title_index': 'par Type',
        'col1_heading': _('User'),
        'chart_type': 'bar'
    },
    USER_BILLING: {
        'title': 'Utilisateur par Facturation',
        'title_index': 'par Facturation',
        'col1_heading': _('User'),
        'chart_type': 'bar'
    },
    USER_MONTH: {
        'title': _('User by Month'),
        'title_index': _('by Month'),
        'col1_heading': _('User'),
        'chart_type': 'date'
    },
    QUEUE_PRIORITY: {
        'title': _('Queue by Priority'),
        'title_index': _('by Priority'),
        'col1_heading': _('Queue'),
        'chart_type': 'bar'
    },
    QUEUE_STATUS: {
        'title': _('Queue by Status'),
        'title_index': _('by Status'),
        'col1_heading': _('Queue'),
        'chart_type': 'bar'
    },
    QUEUE_CATEGORY: {
        'title': 'File par Catégorie',
        'title_index': 'par Catégorie',
        'col1_heading': _('Queue'),
        'chart_type': 'bar'
    },
    QUEUE_TYPE: {
        'title': 'File par Type',
        'title_index': 'par Type',
        'col1_heading': _('Queue'),
        'chart_type': 'bar'
    },
    QUEUE_BILLING: {
        'title': 'File par Facturation',
        'title_index': 'par Facturation',
        'col1_heading': _('Queue'),
        'chart_type': 'bar'
    },
    QUEUE_MONTH: {
        'title': _('Queue by Month'),
        'title_index': _('by Month'),
        'col1_heading': _('Queue'),
        'chart_type': 'date'
    },
    DAYS_UNTIL_TICKET_CLOSED_BY_MONTH: {
        'title': _('Days until ticket closed by Month'),
        'title_index': _('Days until ticket closed by Month'),
        'col1_heading': _('Queue'),
        'chart_type': 'date'
    }
}


@staff_member_required
def report_index(request):
    number_tickets = Ticket.objects.count()
    saved_query = request.GET.get('saved_query')

    user_queues = _get_user_queues(request.user)
    tickets = Ticket.objects.filter(queue__in=user_queues)
    basic_ticket_stats = calc_basic_ticket_stats(tickets)

    # The following query builds a grid of queues & ticket statuses,
    # to be displayed to the user. EG:
    #          Open  Resolved
    # Queue 1    10     4
    # Queue 2     4    12
    queues = user_queues if user_queues else Queue.objects.all()

    # Filter results with a date range picker
    from_date, to_date = handle_date_range_picker_filter(request.POST.get('dateRange'))

    dash_tickets = []
    for queue in queues:
        ticket_set = queue.ticket_set.filter(created__date__range=(from_date, to_date))

        dash_ticket = {
            'id': queue.id,
            'name': queue.title,
            'open': ticket_set.filter(status__in=(1, 2)).count(),
            'resolved': ticket_set.filter(status=3).count(),
            'closed': ticket_set.filter(status__in=(4, 5)).count(),
        }

        # Calculation of the tickets first answer time average
        total_first_answer_times = timedelta()
        number_under_one_hour = []
        for ticket in ticket_set:
            first_answer_time = ticket.get_time_first_answer()
            if first_answer_time:
                total_first_answer_times += first_answer_time
                number_under_one_hour.append(first_answer_time < timedelta(hours=1))
        count = len(number_under_one_hour)
        if count > 0:
            dash_ticket['first_answer_time_average'] = total_first_answer_times / count
            dash_ticket['percentage_uner_one_hour'] = round(number_under_one_hour.count(True) / count * 100)

        dash_tickets.append(dash_ticket)

    return render(request, 'helpdesk/report_index.html', {
        'user_reports': {i: r for i, r in reports.items() if r['col1_heading'] == _('User')},
        'queue_reports': {i: r for i, r in reports.items() if r['col1_heading'] == _('Queue')},
        'number_tickets': number_tickets,
        'saved_query': saved_query,
        'basic_ticket_stats': basic_ticket_stats,
        'dash_tickets': dash_tickets,
        'from': from_date,
        'to': to_date,
        'DAYS_UNTIL_TICKET_CLOSED_BY_MONTH': DAYS_UNTIL_TICKET_CLOSED_BY_MONTH
    })


@staff_member_required
def report_queue(request, queue_id):
    queue = get_object_or_404(_get_user_queues(request.user), id=queue_id)

    # Filter results with a date range picker
    from_date, to_date = handle_date_range_picker_filter(request.POST.get('dateRange'))

    # Prepare status labels
    _OPEN = 'Ouvert'
    _RESOLVED = 'Résolu'
    _CLOSED = 'Fermé'
    status = [_OPEN, _RESOLVED, _CLOSED]

    # Construct data in order to build the Morris chart
    morrisjs_data = []
    for single_date in daterange(from_date, to_date + timedelta(1)):
        datadict = {"x": single_date.strftime("%Y-%m-%d")}
        for i, state in enumerate(status):
            if state == _OPEN:
                datadict[i] = queue.ticket_set.filter(created__date=single_date).count()
            elif state == _RESOLVED:
                datadict[i] = queue.ticket_set.filter(resolved__date=single_date).count()
            elif state == _CLOSED:
                datadict[i] = queue.ticket_set.filter(closed__date=single_date).count()
        morrisjs_data.append(datadict)

    # Count total for each status
    open_total = queue.ticket_set.filter(created__date__range=(from_date, to_date)).count()
    resolved_total = queue.ticket_set.filter(resolved__date__range=(from_date, to_date), status__in=[3, 4, 5]).count()
    closed_total = queue.ticket_set.filter(closed__date__range=(from_date, to_date), status__in=[4, 5]).count()
    # Calculate the delta between beginning and end date in days
    delta = (to_date + timedelta(1)) - from_date
    delta = delta.days
    # Compute average values for each status
    open_average = open_total / delta
    resolved_average = resolved_total / delta
    closed_average = closed_total / delta

    return render(request, 'helpdesk/report_queue.html', {
        'queue': queue,
        'from': from_date,
        'to': to_date,
        'open_total': open_total,
        'open_average': open_average,
        'resolved_total': resolved_total,
        'resolved_average': resolved_average,
        'closed_total': closed_total,
        'closed_average': closed_average,
        'morrisjs_data': morrisjs_data,
        'status': status,
    })


@staff_member_required
def run_report(request, report):
    #
    if Ticket.objects.count() == 0:
        messages.info(request, 'Aucun ticket à analyser')
        redirect("helpdesk:report_index")
    if report not in reports.keys():
        messages.error(request, 'Aucun rapport du nom de "%s"' % report)
        return redirect("helpdesk:report_index")

    from_date, to_date = handle_date_range_picker_filter(request.POST.get('dateRange'))

    report_queryset = Ticket.objects.select_related().filter(
        queue__in=_get_user_queues(request.user), created__date__range=(from_date, to_date)
    )
    if report == DAYS_UNTIL_TICKET_CLOSED_BY_MONTH:
        report_queryset = report_queryset.filter(status__in=(Ticket.CLOSED_STATUS, Ticket.DUPLICATE_STATUS))

    from_saved_query = False
    saved_query = None

    if request.GET.get('saved_query'):
        from_saved_query = True
        try:
            saved_query = SavedSearch.objects.get(pk=request.GET.get('saved_query'))
        except SavedSearch.DoesNotExist:
            return HttpResponseRedirect(reverse('helpdesk:report_index'))
        if not (saved_query.shared or saved_query.user == request.user):
            return HttpResponseRedirect(reverse('helpdesk:report_index'))

        import json
        from helpdesk.lib import b64decode
        try:
            if six.PY3:
                if DJANGO_VERSION[0] > 1:
                    # if Django >= 2.0
                    query_params = json.loads(b64decode(str(saved_query.query).lstrip("b\\'")).decode())
                else:
                    query_params = json.loads(b64decode(str(saved_query.query)).decode())
            else:
                query_params = json.loads(b64decode(str(saved_query.query)))
        except json.JSONDecodeError:
            return HttpResponseRedirect(reverse('helpdesk:report_index'))

        report_queryset = apply_query(report_queryset, query_params)

    # Init variables
    table = []
    column_headings = [reports[report]['col1_heading']]
    series_names = []
    morrisjs_data = []

    if not report_queryset:
        messages.info(request, "Le filtre utilisé n'a retourné aucun ticket")
    else:
        from collections import defaultdict
        summarytable = defaultdict(int)
        # a second table for more complex queries
        summarytable2 = defaultdict(int)

        first_ticket = report_queryset.earliest('created')
        first_month = first_ticket.created.month
        first_year = first_ticket.created.year

        last_ticket = report_queryset.latest('created')
        last_month = last_ticket.created.month
        last_year = last_ticket.created.year

        # Prepare periods
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

        # Prepare possible options and add it to column headings
        possible_options = None
        if report == USER_PRIORITY:
            possible_options = [t[1].title() for t in Ticket.PRIORITY_CHOICES]
        elif report == USER_QUEUE:
            queue_options = _get_user_queues(request.user)
            possible_options = [q.title for q in queue_options]
        elif report == USER_STATUS:
            possible_options = [s[1].title() for s in Ticket.STATUS_CHOICES]
        elif report == USER_CATEGORY:
            possible_options = list(TicketCategory.objects.values_list('name', flat=True)) + ['Non définie']
        elif report == USER_TYPE:
            possible_options = list(TicketType.objects.values_list('name', flat=True)) + ['Non défini']
        elif report == USER_BILLING:
            possible_options = [s[1] for s in Ticket.BILLINGS] + ['Non définie']
        elif report == USER_MONTH:
            possible_options = periods
        elif report == QUEUE_PRIORITY:
            possible_options = [t[1].title() for t in Ticket.PRIORITY_CHOICES]
        elif report == QUEUE_STATUS:
            possible_options = [s[1].title() for s in Ticket.STATUS_CHOICES]
        elif report == QUEUE_CATEGORY:
            possible_options = list(TicketCategory.objects.values_list('name', flat=True)) + ['Non définie']
        elif report == QUEUE_TYPE:
            possible_options = list(TicketType.objects.values_list('name', flat=True)) + ['Non défini']
        elif report == QUEUE_BILLING:
            possible_options = [s[1] for s in Ticket.BILLINGS] + ['Non définie']
        elif report == QUEUE_MONTH:
            possible_options = periods
        elif report == DAYS_UNTIL_TICKET_CLOSED_BY_MONTH:
            possible_options = periods
        column_headings += possible_options
        column_headings.append('Total')

        # Calculate each value for each ticket
        metric3 = False
        for ticket in report_queryset:
            if report == USER_PRIORITY:
                metric1 = ticket.get_assigned_to
                metric2 = ticket.get_priority_display()
            elif report == USER_QUEUE:
                metric1 = ticket.get_assigned_to
                metric2 = ticket.queue.title
            elif report == USER_STATUS:
                metric1 = ticket.get_assigned_to
                metric2 = ticket.get_status_display()
            elif report == USER_CATEGORY:
                metric1 = ticket.get_assigned_to
                metric2 = '%s' % (ticket.category if ticket.category else 'Non définie')
            elif report == USER_TYPE:
                metric1 = ticket.get_assigned_to
                metric2 = '%s' % (ticket.type if ticket.type else 'Non défini')
            elif report == USER_BILLING:
                metric1 = ticket.get_assigned_to
                metric2 = '%s' % (ticket.get_billing_display() if ticket.billing else 'Non définie')
            elif report == USER_MONTH:
                metric1 = ticket.get_assigned_to
                metric2 = '%s-%s' % (ticket.created.year, ticket.created.month)
            elif report == QUEUE_PRIORITY:
                metric1 = ticket.queue.title
                metric2 = ticket.get_priority_display()
            elif report == QUEUE_STATUS:
                metric1 = ticket.queue.title
                metric2 = ticket.get_status_display()
            elif report == QUEUE_MONTH:
                metric1 = ticket.queue.title
                metric2 = '%s-%s' % (ticket.created.year, ticket.created.month)
            elif report == QUEUE_CATEGORY:
                metric1 = ticket.queue.title
                metric2 = '%s' % (ticket.category if ticket.category else 'Non définie')
            elif report == QUEUE_TYPE:
                metric1 = ticket.queue.title
                metric2 = '%s' % (ticket.type if ticket.type else 'Non défini')
            elif report == QUEUE_BILLING:
                metric1 = ticket.queue.title
                metric2 = '%s' % (ticket.get_billing_display() if ticket.billing else 'Non définie')
            elif report == DAYS_UNTIL_TICKET_CLOSED_BY_MONTH:
                metric1 = ticket.queue.title
                metric2 = '%s-%s' % (ticket.created.year, ticket.created.month)
                metric3 = ticket.modified - ticket.created
                metric3 = metric3.days
            else:
                raise ValueError('%s report is not handled.' % report)

            summarytable[metric1, metric2] += 1
            if metric3:
                if report == DAYS_UNTIL_TICKET_CLOSED_BY_MONTH:
                    summarytable2[metric1, metric2] += metric3

        if report == DAYS_UNTIL_TICKET_CLOSED_BY_MONTH:
            for key in summarytable2.keys():
                summarytable[key] = summarytable2[key] / summarytable[key]

        header1 = sorted({i for i, _ in summarytable.keys()})

        # Pivot the data so that 'header1' fields are always first column
        # in the row, and 'possible_options' are always the 2nd - nth columns.
        totals = {}
        for item in header1:
            data = []
            for column in possible_options:
                value = summarytable[item, column]
                data.append(value)
                # Add value to total for this column
                if column not in totals.keys():
                    totals[column] = value
                else:
                    totals[column] += value
            data.append(sum(data))
            table.append([item] + data)

        # Zip data and headers together in one list for Morris.js charts
        # will get a list like [(Header1, Data1), (Header2, Data2)...]
        seriesnum = 0
        for label in column_headings[1:-1]:
            seriesnum += 1
            datadict = {"x": label}
            for n in range(0, len(table)):
                datadict[n] = table[n][seriesnum]
            morrisjs_data.append(datadict)

        for series in table:
            series_names.append(series[0])

        # Add total row to table
        total_data = []
        for column in possible_options:
            total_data.append(totals[column])
        total_data.append(sum(total_data))
        table.append(['Total'] + total_data)

    return render(request, 'helpdesk/report_output.html', {
        'title': reports[report]['title'],
        'chart_type': reports[report]['chart_type'],
        'data': table,
        'headings': column_headings,
        'series_names': series_names,
        'morrisjs_data': morrisjs_data,
        'from_saved_query': from_saved_query,
        'saved_query': saved_query,
        'from': from_date,
        'to': to_date,
    })


@staff_member_required
def save_query(request):
    title = request.POST.get('title', None)
    shared = request.POST.get('shared', False)
    if shared == 'on':  # django only translates '1', 'true', 't' into True
        shared = True
    query_encoded = request.POST.get('query_encoded', None)

    if not title or not query_encoded:
        return HttpResponseRedirect(reverse('helpdesk:list'))

    query = SavedSearch(title=title, shared=shared, query=query_encoded, user=request.user)
    query.save()

    return HttpResponseRedirect('%s?saved_query=%s' % (reverse('helpdesk:list'), query.id))


@staff_member_required
def delete_saved_query(request, id):
    query = get_object_or_404(SavedSearch, id=id, user=request.user)

    if request.method == 'POST':
        query.delete()
        return HttpResponseRedirect(reverse('helpdesk:list'))
    else:
        return render(request, 'helpdesk/confirm_delete_saved_query.html', {'query': query})


@staff_member_required
def user_settings(request):
    s = request.user.usersettings_helpdesk
    if request.POST:
        form = UserSettingsForm(request.POST)
        if form.is_valid():
            s.settings = form.cleaned_data
            s.save()
    else:
        form = UserSettingsForm(s.settings)

    return render(request, 'helpdesk/user_settings.html', {'form': form})


@superuser_required
def email_ignore(request):
    return render(request, 'helpdesk/email_ignore_list.html', {
        'ignore_list': IgnoreEmail.objects.all(),
    })


@superuser_required
def email_ignore_add(request):
    if request.method == 'POST':
        form = EmailIgnoreForm(request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('helpdesk:email_ignore'))
    else:
        form = EmailIgnoreForm(request.GET)

    return render(request, 'helpdesk/email_ignore_add.html', {'form': form})


@superuser_required
def email_ignore_del(request, id):
    ignore = get_object_or_404(IgnoreEmail, id=id)
    if request.method == 'POST':
        ignore.delete()
        return HttpResponseRedirect(reverse('helpdesk:email_ignore'))
    else:
        return render(request, 'helpdesk/email_ignore_del.html', {'ignore': ignore})


@staff_member_required
def ticket_cc(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if not _has_access_to_queue(request.user, ticket.queue):
        raise PermissionDenied()
    if not _is_my_ticket(request.user, ticket):
        raise PermissionDenied()

    copies_to = ticket.ticketcc_set.all()
    return render(request, 'helpdesk/ticket_cc_list.html', {
        'copies_to': copies_to,
        'ticket': ticket,
    })


@staff_member_required
def ticket_cc_add(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if not _has_access_to_queue(request.user, ticket.queue):
        raise PermissionDenied()
    if not _is_my_ticket(request.user, ticket):
        raise PermissionDenied()

    form = None
    if request.method == 'POST':
        form = TicketCCForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data.get('user')
            email = form.cleaned_data.get('email')
            if user and ticket.ticketcc_set.filter(user=user).exists():
                form.add_error('user', "Impossible d'ajouter deux fois le même utilisateur")
            elif email and ticket.ticketcc_set.filter(email=email).exists():
                form.add_error('email', "Impossible d'ajouter deux fois la même adresse mail")
            else:
                ticketcc = form.save(commit=False)
                ticketcc.ticket = ticket
                ticketcc.save()
                return HttpResponseRedirect(
                    reverse('helpdesk:ticket_cc', kwargs={'ticket_id': ticket.id})
                )

    return render(request, 'helpdesk/ticket_cc_add.html', {
        'ticket': ticket,
        'form': form,
        'form_email': TicketCCEmailForm(),
        'form_user': TicketCCUserForm(),
    })


@staff_member_required
def ticket_cc_del(request, ticket_id, cc_id):
    cc = get_object_or_404(TicketCC, ticket__id=ticket_id, id=cc_id)

    if request.method == 'POST':
        cc.delete()
        return HttpResponseRedirect(reverse('helpdesk:ticket_cc',
                                            kwargs={'ticket_id': cc.ticket.id}))
    return render(request, 'helpdesk/ticket_cc_del.html', {'cc': cc})


@staff_member_required
def ticket_dependency_add(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if not _has_access_to_queue(request.user, ticket.queue):
        raise PermissionDenied()
    if not _is_my_ticket(request.user, ticket):
        raise PermissionDenied()

    form = TicketDependencyForm(request.POST or None)
    # A ticket cannot depends on itself or on a ticket already depending on it
    form.fields['depends_on'].queryset = Ticket.objects.exclude(
        Q(id=ticket.id) | Q(ticketdependency__depends_on=ticket)
    )
    if form.is_valid():
        ticketdependency = form.save(commit=False)
        ticketdependency.ticket = ticket
        ticketdependency.save()
        return redirect(ticket)
    return render(request, 'helpdesk/ticket_dependency_add.html', {
        'ticket': ticket,
        'form': form,
    })


@staff_member_required
def ticket_dependency_del(request, ticket_id, dependency_id):
    dependency = get_object_or_404(TicketDependency, ticket__id=ticket_id, id=dependency_id)
    if request.method == 'POST':
        dependency.delete()
        return HttpResponseRedirect(reverse('helpdesk:view', args=[ticket_id]))
    return render(request, 'helpdesk/ticket_dependency_del.html', {'dependency': dependency})


@staff_member_required
def attachment_del(request, ticket_id, attachment_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if not _has_access_to_queue(request.user, ticket.queue):
        raise PermissionDenied()
    if not _is_my_ticket(request.user, ticket):
        raise PermissionDenied()

    attachment = get_object_or_404(Attachment, id=attachment_id)
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
    # all not closed tickets (open, reopened, resolved) - independent of user
    all_open_tickets = Tickets.exclude(status__in=(Ticket.CLOSED_STATUS, Ticket.DUPLICATE_STATUS))
    today = datetime.today()

    date_30 = date_rel_to_today(today, 30)
    date_60 = date_rel_to_today(today, 60)
    date_30_str = date_30.strftime('%Y-%m-%d')
    date_60_str = date_60.strftime('%Y-%m-%d')

    # > 0 & <= 30
    ota_le_30 = all_open_tickets.filter(created__gte=date_30_str)
    N_ota_le_30 = len(ota_le_30)

    # >= 30 & <= 60
    ota_le_60_ge_30 = all_open_tickets.filter(created__gte=date_60_str, created__lte=date_30_str)
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
    all_closed_tickets = Tickets.filter(status__in=(Ticket.CLOSED_STATUS, Ticket.DUPLICATE_STATUS))
    average_nbr_days_until_ticket_closed = \
        calc_average_nbr_days_until_ticket_resolved(all_closed_tickets)
    # all closed tickets that were opened in the last 60 days.
    all_closed_last_60_days = all_closed_tickets.filter(created__gte=date_60_str)
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


def feedback_survey_list(request):
    queryset = FeedbackSurvey.objects.order_by('-created_at')

    f = FeedbackSurveyFilter(request.GET, queryset=queryset)

    page = request.GET.get('page', 1)

    paginator = Paginator(f.qs, 20)
    try:
        feedback_surveys = paginator.page(page)
    except PageNotAnInteger:
        feedback_surveys = paginator.page(1)
    except EmptyPage:
        feedback_surveys = paginator.page(paginator.num_pages)

    return render(request, 'helpdesk/feedback_survey_list.html', {
        'filter': f,
        'feedback_surveys': feedback_surveys,
    })
