"""                                     .. 
Jutda Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

forms.py - Definitions of newforms-based forms for creating and maintaining 
           tickets.
"""

from django import newforms as forms
from helpdesk.models import Ticket, Queue, FollowUp
from django.contrib.auth.models import User
from datetime import datetime

class TicketForm(forms.Form):
    queue = forms.ChoiceField(label=u'Queue', required=True, choices=())

    title = forms.CharField(max_length=100, required=True,
                           widget=forms.TextInput(),
                           label=u'Summary of the problem')
    
    submitter_email = forms.EmailField(required=False,
                            label=u'Submitter E-Mail Address',
                            help_text=u'This e-mail address will receive copies of all public updates to this ticket.')
    
    body = forms.CharField(widget=forms.Textarea(),
                           label=u'Description of Issue', required=True)
    
    assigned_to = forms.ChoiceField(choices=(), required=False,
                           label=u'Case owner',
                           help_text=u'If you select an owner other than yourself, they\'ll be e-mailed details of this ticket immediately.')

    priority = forms.ChoiceField(choices=Ticket.PRIORITY_CHOICES,
                            required=False,
                            initial='3',
                            label=u'Priority',
                            help_text=u'Please select a priority carefully. If unsure, leave it as \'3\'.')
    
    def save(self, user):
        """
        Writes and returns a Ticket() object
        
        """
        q = Queue.objects.get(id=int(self.cleaned_data['queue']))
        
        t = Ticket( title = self.cleaned_data['title'], 
                    submitter_email = self.cleaned_data['submitter_email'],
                    created = datetime.now(),
                    status = Ticket.OPEN_STATUS,
                    queue = q,
                    description = self.cleaned_data['body'],
                    priority = self.cleaned_data['priority'],
                  )
        
        if self.cleaned_data['assigned_to']:
            try:
                u = User.objects.get(id=self.cleaned_data['assigned_to'])
                t.assigned_to = u
            except:
                t.assigned_to = None
        t.save()

        f = FollowUp(   ticket = t,
                        title = 'Ticket Opened',
                        date = datetime.now(),
                        public = True,
                        comment = self.cleaned_data['body'],
                        user = user,
                     )
        if self.cleaned_data['assigned_to']:
            f.title = 'Ticket Opened & Assigned to %s' % t.get_assigned_to

        f.save()
        
        context = {
            'ticket': t,
            'queue': q,
        }

        from helpdesk.lib import send_templated_mail

        if t.submitter_email:
            send_templated_mail('newticket_submitter', context, recipients=t.submitter_email, sender=q.from_address, fail_silently=True)

        if t.assigned_to and t.assigned_to != user:
            send_templated_mail('assigned_owner', context, recipients=t.assigned_to.email, sender=q.from_address, fail_silently=True)

        if q.new_ticket_cc:
            send_templated_mail('newticket_cc', context, recipients=q.new_ticket_cc, sender=q.from_address, fail_silently=True)
        
        if q.updated_ticket_cc and q.updated_ticket_cc != q.new_ticket_cc:
            send_templated_mail('newticket_cc', context, recipients=q.updated_ticket_cc, sender=q.from_address, fail_silently=True)

        return t

class PublicTicketForm(forms.Form):
    queue = forms.ChoiceField(label=u'Queue', required=True, choices=())

    title = forms.CharField(max_length=100, required=True,
                            widget=forms.TextInput(),
                            label=u'Summary of your query')
    
    submitter_email = forms.EmailField(required=True,
                            label=u'Your E-Mail Address',
                            help_text=u'We will e-mail you when your ticket is updated.')
    
    body = forms.CharField(widget=forms.Textarea(),
                            label=u'Description of your issue', required=True,
                            help_text=u'Please be as descriptive as possible, including any details we may need to address your query.')
    
    priority = forms.ChoiceField(choices=Ticket.PRIORITY_CHOICES,
                            required=True,
                            initial='3',
                            label=u'Urgency',
                            help_text=u'Please select a priority carefully.')
    
    def save(self):
        """
        Writes and returns a Ticket() object
        
        """
        q = Queue.objects.get(id=int(self.cleaned_data['queue']))
        
        t = Ticket( title = self.cleaned_data['title'], 
                    submitter_email = self.cleaned_data['submitter_email'],
                    created = datetime.now(),
                    status = Ticket.OPEN_STATUS,
                    queue = q,
                    description = self.cleaned_data['body'],
                    priority = self.cleaned_data['priority'],
                  )
        
        t.save()

        f = FollowUp(   ticket = t,
                        title = 'Ticket Opened Via Web',
                        date = datetime.now(),
                        public = True,
                        comment = self.cleaned_data['body'],
                     )

        f.save()
        
        context = {
            'ticket': t,
            'queue': q,
        }

        from helpdesk.lib import send_templated_mail
        send_templated_mail('newticket_submitter', context, recipients=t.submitter_email, sender=q.from_address, fail_silently=True)

        if q.new_ticket_cc:
            send_templated_mail('newticket_cc', context, recipients=q.new_ticket_cc, sender=q.from_address, fail_silently=True)
        
        if q.updated_ticket_cc and q.updated_ticket_cc != q.new_ticket_cc:
            send_templated_mail('newticket_cc', context, recipients=q.updated_ticket_cc, sender=q.from_address, fail_silently=True)

        return t
