"""
Jutda Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/public.py - All public facing views, eg non-staff (no authentication
                  required) views.
"""
from datetime import datetime

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import loader, Context, RequestContext
from django.utils.translation import ugettext as _

from helpdesk.forms import PublicTicketForm
from helpdesk.lib import send_templated_mail
from helpdesk.models import Ticket, Queue

def homepage(request):
    if request.user.is_authenticated():
        return HttpResponseRedirect(reverse('helpdesk_dashboard'))
    
    if request.method == 'POST':
        form = PublicTicketForm(request.POST)
        form.fields['queue'].choices = [('', '--------')] + [[q.id, q.title] for q in Queue.objects.filter(allow_public_submission=True)]
        if form.is_valid():
            ticket = form.save()
            return HttpResponseRedirect('%s?ticket=%s&email=%s'% (reverse('helpdesk_public_view'), ticket.ticket_for_url, ticket.submitter_email))
    else:
        form = PublicTicketForm()
        form.fields['queue'].choices = [('', '--------')] + [[q.id, q.title] for q in Queue.objects.filter(allow_public_submission=True)]

    return render_to_response('helpdesk/public_homepage.html',
        RequestContext(request, {
            'form': form,
        }))

def view_ticket(request):
    ticket = request.GET.get('ticket', '')
    email = request.GET.get('email', '')
    error_message = ''

    if ticket and email:
        try:
            queue, ticket_id = ticket.split('-')
            t = Ticket.objects.get(id=ticket_id, queue__slug__iexact=queue, submitter_email__iexact=email)
            return render_to_response('helpdesk/public_view_ticket.html', 
                RequestContext(request, {'ticket': t,}))
        except:
            t = False;
            error_message = _('Invalid ticket ID or e-mail address. Please try again.')

    return render_to_response('helpdesk/public_view_form.html', 
        RequestContext(request, {
            'ticket': ticket,
            'email': email,
            'error_message': error_message,
        }))
