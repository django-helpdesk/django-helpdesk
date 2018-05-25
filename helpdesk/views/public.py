"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/public.py - All public facing views, eg non-staff (no authentication
                  required) views.
"""
from django import forms
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.utils.http import urlquote
from django.utils.translation import ugettext as _
from django.conf import settings

from helpdesk import settings as helpdesk_settings
from helpdesk.decorators import protect_view
from helpdesk.forms import PublicTicketForm
from helpdesk.models import Ticket, Queue, UserSettings, KBCategory


@protect_view
def view_ticket(request):
    ticket_req = request.GET.get('ticket', None)
    email = request.GET.get('email', None)
    # If there is no email address in the query string, get it from
    # the currently logged-in user
    if not email:
        email = request.user.email

    if ticket_req and email:
        queue, ticket_id = Ticket.queue_and_id_from_query(ticket_req)
        try:
            ticket = Ticket.objects.get(Q(id=ticket_id) & (Q(submitter_email__iexact=email) | Q(viewable_globally=True)))
        except ObjectDoesNotExist:
            error_message = _('Invalid ticket ID or e-mail address. Please try again.')
        except ValueError:
            error_message = _('Invalid ticket ID or e-mail address. Please try again.')
        else:
            if request.user.is_staff:
                redirect_url = reverse('helpdesk:view', args=[ticket_id])
                if 'close' in request.GET:
                    redirect_url += '?close'
                return HttpResponseRedirect(redirect_url)

            if 'close' in request.GET and ticket.status == Ticket.RESOLVED_STATUS:
                from helpdesk.views.staff import update_ticket
                # Trick the update_ticket() view into thinking it's being called with
                # a valid POST.
                request.POST = {
                    'new_status': Ticket.CLOSED_STATUS,
                    'public': 1,
                    'title': ticket.title,
                    'comment': _('Submitter accepted resolution and closed ticket'),
                }
                if ticket.assigned_to:
                    request.POST['owner'] = ticket.assigned_to.id
                request.GET = {}

                return update_ticket(request, ticket_id, public=True)

            # redirect user back to this ticket if possible.
            redirect_url = ''
            if helpdesk_settings.HELPDESK_NAVIGATION_ENABLED:
                redirect_url = reverse('helpdesk:view', args=[ticket_id])

            return render(request, 'helpdesk/public_view_ticket.html', {
                'ticket': ticket,
                'helpdesk_settings': helpdesk_settings,
                'next': redirect_url,
            })
    elif ticket_req is None and email is None:
        error_message = None
    else:
        error_message = _('Missing ticket ID or e-mail address. Please try again.')

    return render(request, 'helpdesk/public_view_form.html', {
        'ticket': False,
        'email': email,
        'error_message': error_message,
        'helpdesk_settings': helpdesk_settings,
    })


def change_language(request):
    return_to = ''
    if 'return_to' in request.GET:
        return_to = request.GET['return_to']

    return render(request, 'helpdesk/public_change_language.html', {'next': return_to})
