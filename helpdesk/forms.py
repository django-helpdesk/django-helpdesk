"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

forms.py - Definitions of newforms-based forms for creating and maintaining
           tickets.
"""


from django.core.exceptions import ObjectDoesNotExist
from django.utils.six import StringIO
from django import forms
from django.forms import widgets
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone

from helpdesk.lib import send_templated_mail, safe_template_context, process_attachments
from helpdesk.models import (Ticket, Queue, FollowUp, Attachment, IgnoreEmail, TicketCC,
                             CustomField, TicketCustomFieldValue, TicketDependency)
from helpdesk import settings as helpdesk_settings

User = get_user_model()

CUSTOMFIELD_TO_FIELD_DICT = {
    # Store the immediate equivalences here
    'boolean': forms.BooleanField,
    'date': forms.DateField,
    'time': forms.TimeField,
    'datetime': forms.DateTimeField,
    'email': forms.EmailField,
    'url': forms.URLField,
    'ipaddress': forms.GenericIPAddressField,
    'slug': forms.SlugField,
}


class CustomFieldMixin(object):
    """
    Mixin that provides a method to turn CustomFields into an actual field
    """

    def customfield_to_field(self, field, instanceargs):
        # if-elif branches start with special cases
        if field.data_type == 'varchar':
            fieldclass = forms.CharField
            instanceargs['max_length'] = field.max_length
        elif field.data_type == 'text':
            fieldclass = forms.CharField
            instanceargs['widget'] = forms.Textarea
            instanceargs['max_length'] = field.max_length
        elif field.data_type == 'integer':
            fieldclass = forms.IntegerField
        elif field.data_type == 'decimal':
            fieldclass = forms.DecimalField
            instanceargs['decimal_places'] = field.decimal_places
            instanceargs['max_digits'] = field.max_length
        elif field.data_type == 'list':
            fieldclass = forms.ChoiceField
            choices = field.choices_as_array
            if field.empty_selection_list:
                choices.insert(0, ('', '---------'))
            instanceargs['choices'] = choices
        else:
            # Try to use the immediate equivalences dictionary
            try:
                fieldclass = CUSTOMFIELD_TO_FIELD_DICT[field.data_type]
            except KeyError:
                # The data_type was not found anywhere
                raise NameError("Unrecognized data_type %s" % field.data_type)

        self.fields['custom_%s' % field.name] = fieldclass(**instanceargs)


class EditTicketForm(CustomFieldMixin, forms.ModelForm):

    class Meta:
        model = Ticket
        exclude = ('created', 'modified', 'status', 'on_hold', 'resolution', 'last_escalation', 'assigned_to')

    def __init__(self, *args, **kwargs):
        """
        Add any custom fields that are defined to the form
        """
        super(EditTicketForm, self).__init__(*args, **kwargs)

        for field in CustomField.objects.all():
            try:
                current_value = TicketCustomFieldValue.objects.get(ticket=self.instance, field=field)
                initial_value = current_value.value
            except TicketCustomFieldValue.DoesNotExist:
                initial_value = None
            instanceargs = {
                'label': field.label,
                'help_text': field.help_text,
                'required': field.required,
                'initial': initial_value,
            }

            self.customfield_to_field(field, instanceargs)

    def save(self, *args, **kwargs):

        for field, value in self.cleaned_data.items():
            if field.startswith('custom_'):
                field_name = field.replace('custom_', '', 1)
                customfield = CustomField.objects.get(name=field_name)
                try:
                    cfv = TicketCustomFieldValue.objects.get(ticket=self.instance, field=customfield)
                except ObjectDoesNotExist:
                    cfv = TicketCustomFieldValue(ticket=self.instance, field=customfield)
                cfv.value = value
                cfv.save()

        return super(EditTicketForm, self).save(*args, **kwargs)


class EditFollowUpForm(forms.ModelForm):

    class Meta:
        model = FollowUp
        exclude = ('date', 'user',)

    def __init__(self, *args, **kwargs):
        """Filter not openned tickets here."""
        super(EditFollowUpForm, self).__init__(*args, **kwargs)
        self.fields["ticket"].queryset = Ticket.objects.filter(status__in=(Ticket.OPEN_STATUS, Ticket.REOPENED_STATUS))


class AbstractTicketForm(CustomFieldMixin, forms.Form):
    """
    Contain all the common code and fields between "TicketForm" and
    "PublicTicketForm". This Form is not intended to be used directly.
    """
    queue = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Queue'),
        required=True,
        choices=()
    )

    title = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label=_('Summary of the problem'),
    )

    body = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control'}),
        label=_('Description of your issue'),
        required=True,
        help_text=_('Please be as descriptive as possible and include all details'),
    )

    priority = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-control'}),
        choices=Ticket.PRIORITY_CHOICES,
        required=True,
        initial='3',
        label=_('Priority'),
        help_text=_("Please select a priority carefully. If unsure, leave it as '3'."),
    )

    due_date = forms.DateTimeField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=False,
        label=_('Due on'),
    )

    attachment = forms.FileField(
        required=False,
        label=_('Attach File'),
        help_text=_('You can attach a file such as a document or screenshot to this ticket.'),
    )

    def _add_form_custom_fields(self, staff_only_filter=None):
        if staff_only_filter is None:
            queryset = CustomField.objects.all()
        else:
            queryset = CustomField.objects.filter(staff_only=staff_only_filter)

        for field in queryset:
            instanceargs = {
                'label': field.label,
                'help_text': field.help_text,
                'required': field.required,
            }

            self.customfield_to_field(field, instanceargs)

    def _create_ticket(self):
        queue = Queue.objects.get(id=int(self.cleaned_data['queue']))

        ticket = Ticket(title=self.cleaned_data['title'],
                        submitter_email=self.cleaned_data['submitter_email'],
                        created=timezone.now(),
                        status=Ticket.OPEN_STATUS,
                        queue=queue,
                        description=self.cleaned_data['body'],
                        priority=self.cleaned_data['priority'],
                        due_date=self.cleaned_data['due_date'],
                        )

        return ticket, queue

    def _create_custom_fields(self, ticket):
        for field, value in self.cleaned_data.items():
            if field.startswith('custom_'):
                field_name = field.replace('custom_', '', 1)
                custom_field = CustomField.objects.get(name=field_name)
                cfv = TicketCustomFieldValue(ticket=ticket,
                                             field=custom_field,
                                             value=value)
                cfv.save()

    def _create_follow_up(self, ticket, title, user=None):
        followup = FollowUp(ticket=ticket,
                            title=title,
                            date=timezone.now(),
                            public=True,
                            comment=self.cleaned_data['body'],
                            )
        if user:
            followup.user = user
        return followup

    def _attach_files_to_follow_up(self, followup):
        files = self.cleaned_data['attachment']
        if files:
            files = process_attachments(followup, [files])
        return files

    @staticmethod
    def _send_messages(ticket, queue, followup, files, user=None):
        context = safe_template_context(ticket)
        context['comment'] = followup.comment

        messages_sent_to = []

        if ticket.submitter_email:
            send_templated_mail(
                'newticket_submitter',
                context,
                recipients=ticket.submitter_email,
                sender=queue.from_address,
                fail_silently=True,
                files=files,
            )
            messages_sent_to.append(ticket.submitter_email)

        if ticket.assigned_to and \
                ticket.assigned_to != user and \
                ticket.assigned_to.usersettings_helpdesk.settings.get('email_on_ticket_assign', False) and \
                ticket.assigned_to.email and \
                ticket.assigned_to.email not in messages_sent_to:
            send_templated_mail(
                'assigned_owner',
                context,
                recipients=ticket.assigned_to.email,
                sender=queue.from_address,
                fail_silently=True,
                files=files,
            )
            messages_sent_to.append(ticket.assigned_to.email)

        if queue.new_ticket_cc and queue.new_ticket_cc not in messages_sent_to:
            send_templated_mail(
                'newticket_cc',
                context,
                recipients=queue.new_ticket_cc,
                sender=queue.from_address,
                fail_silently=True,
                files=files,
            )
            messages_sent_to.append(queue.new_ticket_cc)

        if queue.updated_ticket_cc and \
                queue.updated_ticket_cc != queue.new_ticket_cc and \
                queue.updated_ticket_cc not in messages_sent_to:
            send_templated_mail(
                'newticket_cc',
                context,
                recipients=queue.updated_ticket_cc,
                sender=queue.from_address,
                fail_silently=True,
                files=files,
            )


class TicketForm(AbstractTicketForm):
    """
    Ticket Form creation for registered users.
    """
    submitter_email = forms.EmailField(
        required=False,
        label=_('Submitter E-Mail Address'),
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text=_('This e-mail address will receive copies of all public '
                    'updates to this ticket.'),
    )

    assigned_to = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-control'}),
        choices=(),
        required=False,
        label=_('Case owner'),
        help_text=_('If you select an owner other than yourself, they\'ll be '
                    'e-mailed details of this ticket immediately.'),
    )

    def __init__(self, *args, **kwargs):
        """
        Add any custom fields that are defined to the form.
        """
        super(TicketForm, self).__init__(*args, **kwargs)
        self._add_form_custom_fields()

    def save(self, user=None):
        """
        Writes and returns a Ticket() object
        """

        ticket, queue = self._create_ticket()
        if self.cleaned_data['assigned_to']:
            try:
                u = User.objects.get(id=self.cleaned_data['assigned_to'])
                ticket.assigned_to = u
            except User.DoesNotExist:
                ticket.assigned_to = None
        ticket.save()

        self._create_custom_fields(ticket)

        if self.cleaned_data['assigned_to']:
            title = _('Ticket Opened & Assigned to %(name)s') % {
                'name': ticket.get_assigned_to or _("<invalid user>")
            }
        else:
            title = _('Ticket Opened')
        followup = self._create_follow_up(ticket, title=title, user=user)
        followup.save()

        files = self._attach_files_to_follow_up(followup)
        self._send_messages(ticket=ticket,
                            queue=queue,
                            followup=followup,
                            files=files,
                            user=user)
        return ticket


class PublicTicketForm(AbstractTicketForm):
    """
    Ticket Form creation for all users (public-facing).
    """
    submitter_email = forms.EmailField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=True,
        label=_('Your E-Mail Address'),
        help_text=_('We will e-mail you when your ticket is updated.'),
    )

    def __init__(self, *args, **kwargs):
        """
        Add any (non-staff) custom fields that are defined to the form
        """
        super(PublicTicketForm, self).__init__(*args, **kwargs)
        self._add_form_custom_fields(False)

    def save(self):
        """
        Writes and returns a Ticket() object
        """
        ticket, queue = self._create_ticket()
        if queue.default_owner and not ticket.assigned_to:
            ticket.assigned_to = queue.default_owner
        ticket.save()

        self._create_custom_fields(ticket)

        followup = self._create_follow_up(ticket, title=_('Ticket Opened Via Web'))
        followup.save()

        files = self._attach_files_to_follow_up(followup)
        self._send_messages(ticket=ticket,
                            queue=queue,
                            followup=followup,
                            files=files)
        return ticket


class UserSettingsForm(forms.Form):
    login_view_ticketlist = forms.BooleanField(
        label=_('Show Ticket List on Login?'),
        help_text=_('Display the ticket list upon login? Otherwise, the dashboard is shown.'),
        required=False,
    )

    email_on_ticket_change = forms.BooleanField(
        label=_('E-mail me on ticket change?'),
        help_text=_('If you\'re the ticket owner and the ticket is changed via the web by somebody else, do you want to receive an e-mail?'),
        required=False,
    )

    email_on_ticket_assign = forms.BooleanField(
        label=_('E-mail me when assigned a ticket?'),
        help_text=_('If you are assigned a ticket via the web, do you want to receive an e-mail?'),
        required=False,
    )

    tickets_per_page = forms.ChoiceField(
        label=_('Number of tickets to show per page'),
        help_text=_('How many tickets do you want to see on the Ticket List page?'),
        required=False,
        choices=((10, '10'), (25, '25'), (50, '50'), (100, '100')),
    )

    use_email_as_submitter = forms.BooleanField(
        label=_('Use my e-mail address when submitting tickets?'),
        help_text=_('When you submit a ticket, do you want to automatically '
                    'use your e-mail address as the submitter address? You '
                    'can type a different e-mail address when entering the '
                    'ticket if needed, this option only changes the default.'),
        required=False,
    )


class EmailIgnoreForm(forms.ModelForm):

    class Meta:
        model = IgnoreEmail
        exclude = []


class TicketCCForm(forms.ModelForm):
    ''' Adds either an email address or helpdesk user as a CC on a Ticket. Used for processing POST requests. '''

    class Meta:
        model = TicketCC
        exclude = ('ticket',)

    def __init__(self, *args, **kwargs):
        super(TicketCCForm, self).__init__(*args, **kwargs)
        if helpdesk_settings.HELPDESK_STAFF_ONLY_TICKET_CC:
            users = User.objects.filter(is_active=True, is_staff=True).order_by(User.USERNAME_FIELD)
        else:
            users = User.objects.filter(is_active=True).order_by(User.USERNAME_FIELD)
        self.fields['user'].queryset = users


class TicketCCUserForm(forms.ModelForm):
    ''' Adds a helpdesk user as a CC on a Ticket '''

    def __init__(self, *args, **kwargs):
        super(TicketCCUserForm, self).__init__(*args, **kwargs)
        if helpdesk_settings.HELPDESK_STAFF_ONLY_TICKET_CC:
            users = User.objects.filter(is_active=True, is_staff=True).order_by(User.USERNAME_FIELD)
        else:
            users = User.objects.filter(is_active=True).order_by(User.USERNAME_FIELD)
        self.fields['user'].queryset = users

    class Meta:
        model = TicketCC
        exclude = ('ticket', 'email',)


class TicketCCEmailForm(forms.ModelForm):
    ''' Adds an email address as a CC on a Ticket '''

    def __init__(self, *args, **kwargs):
        super(TicketCCEmailForm, self).__init__(*args, **kwargs)

    class Meta:
        model = TicketCC
        exclude = ('ticket', 'user',)


class TicketDependencyForm(forms.ModelForm):
    ''' Adds a different ticket as a dependency for this Ticket '''

    class Meta:
        model = TicketDependency
        exclude = ('ticket',)
