"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

forms.py - Definitions of newforms-based forms for creating and maintaining
           tickets.
"""
import logging
from datetime import datetime, date, time
from decimal import Decimal
from operator import itemgetter

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import validate_email
from django import forms
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.shortcuts import get_object_or_404

from helpdesk.lib import safe_template_context, process_attachments
from helpdesk.models import (Ticket, Queue, FollowUp, IgnoreEmail, TicketCC,
                             CustomField, TicketDependency, UserSettings, KBItem,
                             FormType, is_extra_data)
from helpdesk import settings as helpdesk_settings
from helpdesk.email import create_ticket_cc
from helpdesk.decorators import list_of_helpdesk_staff
import re


logger = logging.getLogger(__name__)
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
    'attachment': forms.FileField,
    # TODO Add foreignkey type here?
}

CUSTOMFIELD_DATE_FORMAT = "%Y-%m-%d"
CUSTOMFIELD_TIME_FORMAT = "%H:%M:%S"
CUSTOMFIELD_DATETIME_FORMAT = f"{CUSTOMFIELD_DATE_FORMAT} {CUSTOMFIELD_TIME_FORMAT}"


def _field_ordering(queryset):
    # ordering fields based on form_ordering
    # if form_ordering is None, field is sorted to end of list
    ordering = sorted(
        queryset.values('field_name', 'form_ordering'),
        key=lambda x: float('inf') if x['form_ordering'] is None else x['form_ordering']
    )
    ordering = [
        "e_%s" % field['field_name'] if is_extra_data(field['field_name'])
        else field['field_name']
        for field in ordering
    ]
    return ordering


class CustomFieldMixin(object):
    """
    Mixin that provides a method to turn CustomFields into an actual field
    """

    def customfield_to_field(self, field, instanceargs):
        # Field is an object in CustomField, with attributes like field_name, label, help_text, etc
        # instanceargs dict is for the frontend display settings like max_length, the kind of form widget, etc
        # Use TextInput widget by default
        instanceargs['widget'] = forms.TextInput(attrs={'class': 'form-control'})
        # if-elif branches start with special cases
        if field.data_type is None:
            fieldclass = forms.NullBooleanField
        elif field.data_type == 'varchar':
            fieldclass = forms.CharField
            instanceargs['max_length'] = field.max_length
        elif field.data_type == 'text':
            fieldclass = forms.CharField
            instanceargs['widget'] = forms.Textarea(attrs={'class': 'form-control'})
            instanceargs['max_length'] = field.max_length
        elif field.data_type == 'integer':
            fieldclass = forms.IntegerField
            instanceargs['widget'] = forms.NumberInput(attrs={'class': 'form-control'})
        elif field.data_type == 'decimal':
            fieldclass = forms.DecimalField
            instanceargs['decimal_places'] = field.decimal_places
            instanceargs['max_digits'] = field.max_length
            instanceargs['widget'] = forms.NumberInput(attrs={'class': 'form-control'})
        elif field.data_type == 'list':
            fieldclass = forms.ChoiceField
            choices = field.choices_as_array
            if field.empty_selection_list:
                choices.insert(0, ('', '---------'))
            instanceargs['choices'] = choices
            instanceargs['widget'] = forms.Select(attrs={'class': 'form-control'})
        else:
            # Try to use the immediate equivalences dictionary
            try:
                fieldclass = CUSTOMFIELD_TO_FIELD_DICT[field.data_type]
                # Change widgets for the following classes
                if fieldclass == forms.DateField:
                    instanceargs['widget'] = forms.DateInput(attrs={'class': 'form-control date-field', 'autocomplete': 'off'})
                elif fieldclass == forms.DateTimeField:
                    instanceargs['widget'] = forms.DateTimeInput(attrs={'class': 'form-control datetime-field', 'autocomplete': 'off'})
                elif fieldclass == forms.TimeField:
                    instanceargs['widget'] = forms.TimeInput(attrs={'class': 'form-control time-field', 'autocomplete': 'off'})
                elif fieldclass == forms.BooleanField:
                    instanceargs['widget'] = forms.CheckboxInput(attrs={'class': 'form-control'})
                elif fieldclass == forms.FileField:
                    instanceargs['widget'] = forms.FileInput(attrs={'class': 'form-control-file'})

            except KeyError:
                # The data_type was not found anywhere
                raise NameError("Unrecognized data_type %s" % field.data_type)

        # TODO change this
        if is_extra_data(field.field_name):
            self.fields['e_%s' % field.field_name] = fieldclass(**instanceargs)
        else:
            self.fields[field.field_name] = fieldclass(**instanceargs)


class EditTicketForm(CustomFieldMixin, forms.ModelForm):

    class Meta:
        model = Ticket
        exclude = ('assigned_to', 'created', 'modified', 'status', 'on_hold', 'resolution', 'last_escalation',
                   'organization', 'ticket_form', 'beam_property', 'beam_taxlot')

    class Media:
        js = ('helpdesk/js/init_due_date.js', 'helpdesk/js/init_datetime_classes.js', 'helpdesk/js/validate.js')

    def __init__(self, *args, **kwargs):
        """
        Add any custom fields that are defined to the form
        """
        super(EditTicketForm, self).__init__(*args, **kwargs)
        form_id = self.instance.ticket_form.pk
        extra_data = self.instance.extra_data

        # CustomField already excludes builtin_fields and SEED fields
        display_objects = CustomField.objects.filter(ticket_form=form_id).exclude(field_name='queue')

        # Manually add in queue, not doing so would show all queues
        queues = Queue.objects.filter(organization=self.instance.ticket_form.organization)
        setattr(self.fields['queue'], 'queryset', queues)

        # Disable and add help_text to the merged_to field on this form
        self.fields['merged_to'].disabled = True
        self.fields['merged_to'].help_text = _('This ticket is merged into the selected ticket.')

        for display_data in display_objects:
            initial_value = None

            # if a built-in ticket field shouldn't be editable on this page, add its field name to this list to exclude it
            if is_extra_data(display_data.field_name):
                try:
                    initial_value = extra_data[display_data.field_name]
                    # Attempt to convert from fixed format string to date/time data type
                    if 'datetime' == display_data.data_type:
                        initial_value = datetime.strptime(initial_value, CUSTOMFIELD_DATETIME_FORMAT)
                    elif 'date' == display_data.data_type:
                        initial_value = datetime.strptime(initial_value, CUSTOMFIELD_DATE_FORMAT)
                    elif 'time' == display_data.data_type:
                        initial_value = datetime.strptime(initial_value, CUSTOMFIELD_TIME_FORMAT)
                    # If it is boolean field, transform the value to a real boolean instead of a string
                    elif 'boolean' == display_data.data_type:
                        if isinstance(initial_value, str):
                            initial_value = 'True' == initial_value
                except (KeyError, ValueError, TypeError):  # TicketCustomFieldValue.DoesNotExist,
                    # ValueError error if parsing fails, using initial_value = current_value.value
                    # TypeError if parsing None type
                    pass
                instanceargs = {
                    'label': '%s (Required)' % display_data.label if display_data.required else display_data.label,
                    'help_text': display_data.get_markdown(),
                    'required': display_data.required,
                    'initial': initial_value,
                }
                self.customfield_to_field(display_data, instanceargs)

            elif display_data.field_name in self.fields:
                # if a built-in ticket field shouldn't be editable on this page, add its field name to this list
                if display_data.field_name in ['attachment', 'cc_emails']:
                    self.fields[display_data.field_name].widget = forms.HiddenInput()
                else:
                    attrs = ['label', 'help_text', 'list_values', 'required', 'data_type']
                    for attr in attrs:
                        display_info = getattr(display_data, attr, None)
                        if display_info is not None and display_info != '':
                            if attr == 'help_text':
                                setattr(self.fields[display_data.field_name], attr, display_data.get_markdown())
                            elif attr == 'data_type':
                                if display_info == 'datetime' or display_info == 'time' or display_info == 'date':
                                    self.fields[display_data.field_name].widget.attrs.update({'autocomplete': 'off'})
                            elif attr == 'label':
                                setattr(self.fields[display_data.field_name], attr,
                                        '%s (Required)' % display_info if display_data.required else display_info)
                            else:
                                setattr(self.fields[display_data.field_name], attr, display_info)

        display_list = list(display_objects.values_list('field_name', flat=True))
        for field_name in self.fields.keys():
            if field_name not in ['merged_to', 'secret_key', 'submitter_email', 'extra_data', 'queue',
                                  'kbitem', 'title', 'description'] and (
                    field_name not in display_list and field_name.replace('e_', '', 1) not in display_list):
                self.fields[field_name].widget = forms.HiddenInput()

        if 'title' not in display_list:
            setattr(self.fields['title'], 'required', False)
        self.fields['extra_data'].widget = forms.HiddenInput()

        self.order_fields(_field_ordering(display_objects))

    def clean(self):
        cleaned_data = super(EditTicketForm, self).clean()
        for field, value in cleaned_data.items():
            if field.startswith('e_'):
                field_name = field.replace('e_', '', 1)
                # Convert date/time data type to known fixed format string.
                if datetime is type(value):
                    value = value.strftime(CUSTOMFIELD_DATETIME_FORMAT)
                elif date is type(value):
                    value = value.strftime(CUSTOMFIELD_DATE_FORMAT)
                elif time is type(value):
                    value = value.strftime(CUSTOMFIELD_TIME_FORMAT)
                elif Decimal is type(value):
                    value = str(value)
                cleaned_data['extra_data'][field_name] = value
        return cleaned_data


class EditFollowUpForm(forms.ModelForm):

    class Meta:
        model = FollowUp
        exclude = ('date', 'user',)

    def __init__(self, *args, **kwargs):
        """Filter for Tickets belonging to the current Org."""
        super(EditFollowUpForm, self).__init__(*args, **kwargs)

        t = kwargs['initial']['ticket'] if kwargs else Ticket.objects.filter(id=args[0]['ticket']).first()
        self.fields['ticket'].queryset = Ticket.objects.filter(queue__organization__id=t.queue.organization_id)


class AbstractTicketForm(CustomFieldMixin, forms.Form):
    """
    Contain all the common code and fields between "TicketForm" and
    "PublicTicketForm". This Form is not intended to be used directly.
    """
    # TODO clean up form fields
    form_id = None
    form_title = None
    form_introduction = None
    form_queue = None
    hidden_fields = []

    queue = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Queue'),
        required=True,
        choices=()
    )
    priority = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-control'}),
        choices=Ticket.PRIORITY_CHOICES,
        initial=getattr(settings, 'HELPDESK_PUBLIC_TICKET_PRIORITY', '3'),
        required=False
    )
    attachment = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control-file', 'multiple': True}),
        required=False
    )
    # TODO add beam_property and beam_taxlot so they can be viewed on the staff-side ticket page

    class Media:
        js = ('helpdesk/js/init_due_date.js', 'helpdesk/js/init_datetime_classes.js', 'helpdesk/js/validate.js')

    def __init__(self, kbcategory=None, *args, **kwargs):
        self.form_id = kwargs.pop("form_id")
        super().__init__(*args, **kwargs)

        form = FormType.objects.get(pk=self.form_id)
        self.form_title = form.name
        self.form_introduction = form.get_markdown()
        self.form_queue = form.queue
        if form.queue:
            del self.fields['queue']

        self.files = kwargs.get('files')

        if kbcategory:
            self.fields['kbitem'] = forms.ChoiceField(
                widget=forms.Select(attrs={'class': 'form-control'}),
                required=False,
                label=_('Knowledge Base Item'),
                choices=[(kbi.pk, kbi.title) for kbi in KBItem.objects.filter(category=kbcategory.pk, enabled=True)],
            )

    def clean(self):
        cleaned_data = super(AbstractTicketForm, self).clean()

        # for hidden fields required by helpdesk code, like description
        for field, type_ in self.hidden_fields:
            if 'e_%s' % field in self.errors:
                field = 'e_%s' % field
            if field in self.errors:
                cleaned_data[field] = '' if type_ in ['varchar', 'text', 'email'] else None
                del self._errors[field]

        form = FormType.objects.get(id=self.form_id)
        if form.queue:
            cleaned_data['queue'] = form.queue.id
        elif 'queue' in cleaned_data and cleaned_data['queue'] is None:  # if the queue field is missing from the form
            if self.fields['queue'].choices:
                queue_id = self.fields['queue'].choices[1][0]
                if Queue.objects.filter(id=int(queue_id)).first():
                    cleaned_data['queue'] = int(queue_id)
            else:
                queue = Queue.objects.filter(organization_id=form.organization.id).first()
                if queue:
                    cleaned_data['queue'] = queue.id

        # Clean up extra_data so it can go in json field
        for field in cleaned_data:
            if field.startswith('e_'):
                value = cleaned_data[field]
                if isinstance(value, datetime):
                    value = value.strftime(CUSTOMFIELD_DATETIME_FORMAT)
                elif isinstance(value, date):
                    value = value.strftime(CUSTOMFIELD_DATE_FORMAT)
                elif isinstance(value, time):
                    value = value.strftime(CUSTOMFIELD_TIME_FORMAT)
                elif isinstance(value, Decimal):
                    value = str(value)
                cleaned_data[field] = value

        # Reattach files since the attachment field will only parse the first one
        if self.files:
            for k, files in self.files.lists():
                cleaned_data[k] = files


        # Handle DC Pathway Selection Form
        if form.name == 'Pathway Selection':
            self.clean_dc_ps_form()

        # Handle DC Pathway Change Application Form
        if form.name == 'Pathway Change Application':
            self.clean_dc_pca_form()

        # Handle DC Delay of Compliance Request Form
        if form.name == 'Delay of Compliance Request':
            self.clean_dc_delay_of_compliance_form()

        return cleaned_data

    def clean_dc_ps_form(self):
        if self.cleaned_data.get('e_pathway') == 'Alternative Compliance Pathway':
            # Check that e_backup_pathway, and attachment were provided
            fields = [
                ('e_backup_pathway', 'A Backup Pathway is required'),
                ('attachment', 'An attachment is required')
            ]
            for field in fields:
                if not self.cleaned_data.get(field[0]):
                    msg = forms.ValidationError(field[1] + ' if the Alternative Compliance Pathway is selected.')
                    self.add_error(field[0], msg)
        elif self.cleaned_data.get('e_pathway') == 'Standard Target Pathway':
            # check that there are is at least one attachment
            if not self.files.get('attachment'):
                msg = forms.ValidationError('Attachment(s) required if the Standard Target Pathway is selected.')
                self.add_error('attachment', msg)

    def clean_dc_pca_form(self):
        if self.cleaned_data.get('e_new_pathway') == 'Alternative Compliance Pathway':
            # Check that an attachment was provided
            if not self.cleaned_data.get('attachment'):
                self.add_error('attachment', forms.ValidationError('An Attachment is required if Alternative Compliance'
                                                                   ' Pathway is selected for New Pathway Selection'))

    def clean_dc_delay_of_compliance_form(self):
        # If extended_delay_for_QAH, check that attachment_1, type_affordable_housing, attachment_3 were provided
        if self.cleaned_data.get('e_extended_delay_for_QAH'):
            fields = [('e_attachment_1', 'Qualifying Affordable Housing Attachment is required '),
                      ('e_type_affordable_housing', 'Type of Affordable Housing option is required '),
                      ('e_attachment_3', 'Extended Delay Milestone Plan Attachment is required ')
                      ]
            for field in fields:
                if not self.cleaned_data.get(field[0]):
                    msg = forms.ValidationError(
                        field[1] + 'if Extended Delay for Qualified Affordable Housing is selected.')
                    self.add_error(field[0], msg)

    def _get_attachment_fields(self, with_e=False):
        attachment_fields = []
        for field in self.fields:
            if isinstance(self.fields[field], forms.FileField):
                attachment_fields.append(field.replace('e_', '', 1) if
                                         (field.startswith('e_') and not with_e) else field)
        return attachment_fields

    def _create_ticket(self):
        kbitem = None
        if 'kbitem' in self.cleaned_data:
            kbitem = KBItem.objects.get(id=int(self.cleaned_data['kbitem']))

        extra_data = {}
        if 'extra_data' in self.cleaned_data:
            extra_data = self.cleaned_data['extra_data']

        for field, value in self.cleaned_data.items():
            if field.startswith('e_'):
                field_name = field.replace('e_', '', 1)
                extra_data[field_name] = value

        # Remove any attachment fields from extra_data. They will be stored in the first attachment
        attachment_fields = self._get_attachment_fields()
        extra_data = {k: v for k, v in extra_data.items() if k not in attachment_fields}

        ticket_form = FormType.objects.get(pk=self.form_id)
        queue = Queue.objects.get(id=int(self.cleaned_data['queue']))

        ticket = Ticket(
            # TODO Necessary fields
            ticket_form=ticket_form,  # self.cleaned_data['ticket_form'],
            # Default fields + kbitem
            title=self.cleaned_data.get('title', ''),
            submitter_email=self.cleaned_data.get('submitter_email', None),
            created=timezone.now(),
            status=Ticket.NEW_STATUS,
            queue=queue,
            description=self.cleaned_data.get('description', ''),
            priority=self.cleaned_data.get(
                'priority',
                getattr(settings, "HELPDESK_PUBLIC_TICKET_PRIORITY", "3")),
            due_date=self.cleaned_data.get(
                'due_date',
                getattr(settings, "HELPDESK_PUBLIC_TICKET_DUE_DATE", None)
            ) or None,
            kbitem=kbitem,
            # BEAM's default fields
            contact_name=self.cleaned_data.get('contact_name', None),
            contact_email=self.cleaned_data.get('contact_email', None),
            building_name=self.cleaned_data.get('building_name', None),
            building_address=self.cleaned_data.get('building_address', None),
            pm_id=self.cleaned_data.get('pm_id', None),
            building_id=self.cleaned_data.get('building_id', None),
            extra_data=extra_data
        )

        return ticket, queue

    def _create_follow_up(self, ticket, title, user=None):
        followup = FollowUp(ticket=ticket,
                            title=title,
                            date=timezone.now(),
                            public=True,
                            comment=self.cleaned_data.get('description', ''),)
        if user:
            followup.user = user
        return followup

    def _attach_files_to_follow_up(self, followup):
        files = []

        attachment_fields = self._get_attachment_fields(with_e=True)
        for field in attachment_fields:
            file_or_files = self.cleaned_data[field]
            if isinstance(file_or_files, list):
                for file in file_or_files:
                    files.append(file)
            elif file_or_files:
                files.append(file_or_files)

        if files:
            files = process_attachments(followup, files)
        return files

    @staticmethod
    def _send_messages(ticket, queue, followup, files, user=None):
        # Sent when a ticket is saved.
        context = safe_template_context(ticket)
        context['comment'] = followup.comment
        context['private'] = not followup.public

        roles = {'submitter': ('newticket_submitter', context),
                 'queue_new': ('newticket_cc_user', context),
                 'queue_updated': ('newticket_cc_user', context),
                 'cc_users': ('newticket_cc_user', context)}
        if followup.public:
            roles['cc_public'] = ('newticket_cc_public', context)
            roles['extra'] = ('newticket_cc_public', context)
        if ticket.assigned_to and ticket.assigned_to.usersettings_helpdesk.email_on_ticket_assign:
            roles['assigned_to'] = ('assigned_owner', context)

        ticket.send_ticket_mail(
            roles,
            organization=ticket.ticket_form.organization,
            fail_silently=True,
            files=files,
            source="new ticket",
            user=user
        )

    # TODO move this init
    def _add_form_custom_fields(self, staff_filter=None, public_filter=None):
        if self.form_id is not None:
            if staff_filter:
                queryset = CustomField.objects.filter(ticket_form=self.form_id, staff=True)
                hidden_queryset = CustomField.objects.filter(ticket_form=self.form_id, staff=False)
            elif public_filter:
                queryset = CustomField.objects.filter(ticket_form=self.form_id, public=True)
                hidden_queryset = CustomField.objects.filter(ticket_form=self.form_id, public=False)
            else:
                queryset = CustomField.objects.filter(ticket_form=self.form_id)
                hidden_queryset = CustomField.objects.none()

            self.hidden_fields = list(hidden_queryset.values_list('field_name', 'data_type'))

            hidden_ticket_fields = []
            queryset_values = queryset.values_list('field_name', flat=True)
            for field_name in self.fields:
                if field_name not in queryset_values:
                    hidden_ticket_fields.append(field_name)
                    self.hidden_fields.append((field_name, ''))

            if self.form_queue:
                queryset = queryset.exclude(field_name='queue')

            for field in queryset:
                if field.field_name in self.fields:
                    attrs = ['label', 'help_text', 'list_values', 'required', 'data_type']
                    for attr in attrs:
                        display_info = getattr(field, attr, None)
                        if display_info is not None and display_info != '':
                            if attr == 'help_text':
                                setattr(self.fields[field.field_name], attr, field.get_markdown())
                            elif attr == 'data_type':
                                if display_info == 'datetime' or display_info == 'time' or display_info == 'date':
                                    self.fields[field.field_name].widget.attrs.update(
                                        {'autocomplete': 'off'})
                            else:
                                setattr(self.fields[field.field_name], attr, display_info)
                else:
                    instanceargs = {
                        'label': field.label,
                        'help_text': field.get_markdown(),
                        'required': field.required,
                    }
                    self.customfield_to_field(field, instanceargs)
            for field in hidden_queryset:
                if field.field_name not in self.fields:
                    self.customfield_to_field(field, {})
                if is_extra_data(field.field_name):
                    self.fields['e_%s' % field.field_name].widget = forms.HiddenInput()
                else:
                    self.fields[field.field_name].widget = forms.HiddenInput()

            for field_name in hidden_ticket_fields:
                if field_name == 'queue' and not self.form_queue:
                    pass  # option to select queue should always be available if a default is not set.
                elif field_name != 'assigned_to' and field_name != 'submitter_email':
                    self.fields[field_name].widget = forms.HiddenInput()

            self.order_fields(_field_ordering(queryset))

    def _add_cc_emails(self, ticket):
        """
        Given a ticket with the field 'cc_emails' that is a list of email strings, processes those strings
        and adds them to the list of Copied-To emails on the ticket.
        """
        # TODO add in check for HELPDESK_STAFF_ONLY_TICKET_CCS?
        if 'cc_emails' in self.cleaned_data:
            # Parse cc_emails for emails, should be separated by a space at least
            # Could be in format name <email> or simply <email> or email
            # re.findall splits up cc_emails into list of strings that matches regular expression
            emails = re.findall("([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9]{2,3})", self.cleaned_data['cc_emails'])
            valid_emails = []
            for email in emails:
                try:
                    validate_email(email)
                except ValidationError as e:
                    # Invalid email, don't add
                    pass
                else:
                    valid_emails.append(email)

            name_placeholder = [None] * len(valid_emails)
            emails = list(zip(name_placeholder, valid_emails))
            create_ticket_cc(ticket, emails)


class TicketForm(AbstractTicketForm):
    """
    Ticket Form creation for registered users.
    """
    submitter_email = forms.EmailField(
        required=False,
        label=_('Submitter E-Mail Address'),
        widget=forms.TextInput(attrs={'class': 'form-control', 'type': 'email'}),
        help_text=_('This e-mail address will receive copies of all public '
                    'updates to this ticket.'),
    )
    assigned_to = forms.ChoiceField(
        widget=(
            forms.Select(attrs={'class': 'form-control'})
            if not helpdesk_settings.HELPDESK_CREATE_TICKET_HIDE_ASSIGNED_TO
            else forms.HiddenInput()
        ),
        required=False,
        label=_('Case owner'),
        help_text=_('If you select an owner other than yourself, they\'ll be '
                    'e-mailed details of this ticket immediately.'),
        choices=()
    )

    def __init__(self, *args, **kwargs):
        """
        Add any custom fields that are defined to the form.
        """
        queue_choices = kwargs.pop("queue_choices")

        super().__init__(*args, **kwargs)
        self._add_form_custom_fields(staff_filter=True)

        if self.form_queue is None:
            self.fields['queue'].choices = queue_choices

        org = get_object_or_404(FormType, pk=self.form_id).organization
        assignable_users = list_of_helpdesk_staff(org)
        # TODO add back HELPDESK_STAFF_ONLY_TICKET_OWNERS setting
        """
        if helpdesk_settings.HELPDESK_STAFF_ONLY_TICKET_OWNERS:
            staff_ids = [u.id for u in assignable_users if is_helpdesk_staff(u, org=org)]
            assignable_users = assignable_users.filter(id__in=staff_ids)
        """
        assignable_users = assignable_users.order_by(User.USERNAME_FIELD)
        self.fields['assigned_to'].choices = [('', '--------')] + [
            (u.id, (u.get_full_name() or u.get_username())) for u in assignable_users]

    def save(self, user, form_id=None):
        """
        Writes and returns a Ticket() object
        """
        self.form_id = form_id
        ticket, queue = self._create_ticket()

        if self.cleaned_data['assigned_to']:
            try:
                u = User.objects.get(id=self.cleaned_data['assigned_to'])
                ticket.assigned_to = u
            except User.DoesNotExist:
                ticket.assigned_to = None
        elif queue.default_owner and not ticket.assigned_to:
            ticket.assigned_to = queue.default_owner

        self._add_cc_emails(ticket)

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
    # TODO remove this, replace w/ contact email
    submitter_email = forms.EmailField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'type': 'email'}),
        required=True,
        label=_('Your E-Mail Address'),
        help_text=_('We will e-mail you when your ticket is updated.'),
    )

    def __init__(self, hidden_fields=(), readonly_fields=(), *args, **kwargs):
        """
        Add any (non-staff) custom fields that are defined to the form
        """
        super(PublicTicketForm, self).__init__(*args, **kwargs)
        self._add_form_custom_fields(public_filter=True)

        # Hiding fields based on CustomField attributes has already been done; this is hiding based on kwargs
        for field in self.fields.keys():
            if field in hidden_fields:
                self.fields[field].widget = forms.HiddenInput()
            if field in readonly_fields:
                self.fields[field].disabled = True

        org = get_object_or_404(FormType, pk=self.form_id).organization
        public_queues = Queue.objects.filter(allow_public_submission=True, organization=org)

        if len(public_queues) == 0:
            logger.warning("There are no public queues defined - public ticket creation is impossible")

        if self.form_queue is None:
            self.fields['queue'].choices = [('', '--------')] + [
                (q.id, q.title) for q in public_queues]

    def save(self, user, form_id=None):
        """
        Writes and returns a Ticket() object
        """
        self.form_id = form_id
        ticket, queue = self._create_ticket()

        if queue.default_owner and not ticket.assigned_to:
            ticket.assigned_to = queue.default_owner

        self._add_cc_emails(ticket)

        followup = self._create_follow_up(
            ticket, title=_('Ticket Opened Via Web'), user=user)
        followup.save()

        files = self._attach_files_to_follow_up(followup)
        self._send_messages(ticket=ticket,
                            queue=queue,
                            followup=followup,
                            files=files)
        return ticket


class UserSettingsForm(forms.ModelForm):

    class Meta:
        model = UserSettings
        exclude = ['user', 'settings_pickled']


class EmailIgnoreForm(forms.ModelForm):

    class Meta:
        model = IgnoreEmail
        exclude = []


class TicketCCForm(forms.ModelForm):
    """ Adds either an email address or helpdesk user as a CC on a Ticket. Used for processing POST requests. """

    class Meta:
        model = TicketCC
        exclude = ('ticket',)

    def __init__(self, *args, **kwargs):
        super(TicketCCForm, self).__init__(*args, **kwargs)


class TicketCCUserForm(forms.ModelForm):
    """ Adds a helpdesk user as a CC on a Ticket """

    def __init__(self, *args, **kwargs):
        super(TicketCCUserForm, self).__init__(*args, **kwargs)

    class Meta:
        model = TicketCC
        exclude = ('ticket', 'email',)


class TicketCCEmailForm(forms.ModelForm):
    """ Adds an email address as a CC on a Ticket """

    def __init__(self, *args, **kwargs):
        super(TicketCCEmailForm, self).__init__(*args, **kwargs)

    class Meta:
        model = TicketCC
        exclude = ('ticket', 'user',)


class TicketDependencyForm(forms.ModelForm):
    """ Adds a different ticket as a dependency for this Ticket """

    class Meta:
        model = TicketDependency
        exclude = ('ticket',)


class MultipleTicketSelectForm(forms.Form):
    tickets = forms.ModelMultipleChoiceField(
        label=_('Tickets to merge'),
        queryset=Ticket.objects.filter(merged_to=None),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'})
    )

    def clean_tickets(self):
        tickets = self.cleaned_data.get('tickets')
        if len(tickets) < 2:
            raise ValidationError(_('Please choose at least 2 tickets.'))
        if len(tickets) > 4:
            raise ValidationError(_('Impossible to merge more than 4 tickets...'))
        queues = tickets.order_by('queue').distinct().values_list('queue', flat=True)
        if len(queues) != 1:
            raise ValidationError(_('All selected tickets must share the same queue in order to be merged.'))
        return tickets
