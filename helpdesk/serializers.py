from rest_framework import serializers

from helpdesk.models import FollowUp, KBItem, Ticket, Queue
from .lib import format_time_spent
from datetime import datetime
from helpdesk.decorators import is_helpdesk_staff

from django.contrib.humanize.templatetags import humanize

"""
A serializer for the Ticket model, returns data in the format as required by
datatables for ticket_list.html. Called from staff.datatables_ticket_list.

"""


class QueueField(serializers.Field):
    def to_representation(self, value):
        ret = {
            'title': value.title,
            'id': value.id,
        }
        return ret


class DatatablesTicketSerializer(serializers.ModelSerializer):
    ticket = serializers.SerializerMethodField()
    priority = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    row_class = serializers.CharField(source='get_priority_css_class')
    time_spent = serializers.SerializerMethodField()
    queue = QueueField(source='*')
    kbitem = serializers.CharField(source='kbitem.title', allow_null=True, default='')
    extra_data = serializers.JSONField()
    paired_count = serializers.SerializerMethodField()
    last_reply = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = ('ticket',
                  'id',
                  'title',
                  'priority',
                  'queue',
                  'get_status',
                  'created',
                  'last_reply',
                  'due_date',
                  'assigned_to',
                  'submitter_email',
                  'row_class',
                  'time_spent',
                  'kbitem',
                  'extra_data',
                  'paired_count', )

    @staticmethod
    def get_ticket(obj):
        return str(obj.id) + " " + obj.ticket

    @staticmethod
    def get_priority(obj):
        return obj.get_priority[3:]

    @staticmethod
    def get_created(obj):
        created = humanize.naturaltime(obj.created)
        return created.replace(u'\xa0', ' ') if created else created

    @staticmethod
    def get_last_reply(obj):
        date = obj.get_last_followup('')
        if date:
            last_reply = humanize.naturaltime(date)
            return last_reply.replace(u'\xa0', ' ')
        else:
            return ''

    @staticmethod
    def get_due_date(obj):
        due_date = humanize.naturaltime(obj.due_date)
        return due_date.replace(u'\xa0', ' ') if due_date else due_date

    @staticmethod
    def get_assigned_to(obj):
        possible_vals = [*((obj.assigned_to.get_full_name(), obj.assigned_to.email, obj.assigned_to.username)
                           if obj.assigned_to else ()),
                         'None']
        return next(val for val in possible_vals if val)

    @staticmethod
    def get_time_spent(obj):
        return format_time_spent(obj.time_spent)

    @staticmethod
    def get_paired_count(obj):
        return obj.beam_property.count() + obj.beam_taxlot.count()

    def to_representation(self, instance):
        from collections import OrderedDict
        data = super(DatatablesTicketSerializer, self).to_representation(instance)
        new_names = {'get_status': 'status', 'submitter_email': 'submitter'}
        data = OrderedDict((new_names.get(k, k), v if v else '') for k, v in data.items())
        return data


class ReportTicketSerializer(serializers.ModelSerializer):
    formtype = serializers.CharField(source='ticket_form.name')
    created = serializers.DateTimeField(format='%m-%d-%Y %H:%M:%S')
    first_staff_followup = serializers.SerializerMethodField()
    closed_date = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    time_spent = serializers.SerializerMethodField()
    is_followup_required = serializers.SerializerMethodField()
    number_staff_followups = serializers.SerializerMethodField()
    number_public_followups = serializers.SerializerMethodField()
    kbitem = serializers.CharField(source='kbitem.title', allow_null=True, default='')
    merged_to = serializers.SerializerMethodField()
    queue = serializers.CharField(source='queue.title')
    extra_data = serializers.JSONField()

    class Meta:
        model = Ticket
        fields = (
            # Ticket Fields
            'queue',
            'formtype',
            'created',
            'id',
            'title',
            'get_status',
            'submitter_email',
            'description',
            'contact_name',
            'contact_email',
            'building_name',
            'building_address',
            'building_id',
            'pm_id',
            'kbitem',
            # Generated Fields
            'assigned_to',
            'time_spent',
            'merged_to',
            'first_staff_followup',
            'closed_date',
            'is_followup_required',
            'number_staff_followups',
            'number_public_followups',
            'extra_data'
        )

    @staticmethod
    def get_first_staff_followup(obj):
        date = obj.get_last_followup('staff')
        return datetime.strftime(date, '%m-%d-%Y %H:%M:%S') if date else 'None'

    @staticmethod
    def get_closed_date(obj):
        terminal_statuses = [Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS, Ticket.DUPLICATE_STATUS]
        if obj.status in terminal_statuses:
            f = FollowUp.objects.filter(ticket_id=obj.id, new_status__in=terminal_statuses).order_by('date').last()
            return datetime.strftime(f.date, '%m-%d-%Y %H:%M:%S') if f else 'None'
        else:
            return 'None'

    @staticmethod
    def get_assigned_to(obj):
        possible_vals = [*((obj.assigned_to.get_full_name(), obj.assigned_to.email, obj.assigned_to.username)
                           if obj.assigned_to else ()),
                         'None']
        return next(val for val in possible_vals if val)

    @staticmethod
    def get_time_spent(obj):
        return format_time_spent(obj.time_spent)

    @staticmethod
    def get_is_followup_required(obj):
        starting_statuses = [Ticket.OPEN_STATUS, Ticket.REOPENED_STATUS, Ticket.NEW_STATUS]
        return 'Yes' if obj.status in starting_statuses else 'No'

    @staticmethod
    def get_number_staff_followups(obj):
        staff_followups = [f for f in obj.followup_set.all() if is_helpdesk_staff(f.user)]
        return len(staff_followups)

    @staticmethod
    def get_number_public_followups(obj):
        public_followups = [f for f in obj.followup_set.all() if not is_helpdesk_staff(f.user)]
        return len(public_followups)

    @staticmethod
    def get_merged_to(obj):
        return obj.merged_to.queue.title + '-' + str(obj.merged_to.id) if obj.merged_to else ''

