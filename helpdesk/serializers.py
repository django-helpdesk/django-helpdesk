from rest_framework import serializers

from .models import Ticket, FollowUp
from .lib import format_time_spent
from datetime import datetime
from helpdesk.decorators import is_helpdesk_staff

from django.contrib.humanize.templatetags import humanize

"""
A serializer for the Ticket model, returns data in the format as required by
datatables for ticket_list.html. Called from staff.datatables_ticket_list.

"""


class DatatablesTicketSerializer(serializers.ModelSerializer):
    ticket = serializers.SerializerMethodField()
    priority = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    submitter = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    row_class = serializers.SerializerMethodField()
    time_spent = serializers.SerializerMethodField()
    queue = serializers.SerializerMethodField()
    kbitem = serializers.SerializerMethodField()
    extra_data = serializers.SerializerMethodField()
    paired_count = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        # fields = '__all__'
        fields = ('ticket', 'id', 'priority', 'title', 'queue', 'status',
                  'created', 'due_date', 'assigned_to', 'submitter', 'row_class',
                  'time_spent', 'kbitem', 'extra_data', 'paired_count',)

    def get_queue(self, obj):
        return {"title": obj.queue.title, "id": obj.queue.id}

    def get_ticket(self, obj):
        return str(obj.id) + " " + obj.ticket

    def get_priority(self, obj):
        return obj.get_priority[3:]

    def get_status(self, obj):
        return obj.get_status

    def get_created(self, obj):
        created = humanize.naturaltime(obj.created)
        return created.replace(u'\xa0', ' ') if created else created

    def get_due_date(self, obj):
        due_date = humanize.naturaltime(obj.due_date)
        return due_date.replace(u'\xa0', ' ') if due_date else due_date

    def get_assigned_to(self, obj):
        if obj.assigned_to:
            if obj.assigned_to.get_full_name():
                return obj.assigned_to.get_full_name()
            elif obj.assigned_to.email:
                return obj.assigned_to.email
            else:
                return obj.assigned_to.username
        else:
            return "None"

    def get_submitter(self, obj):
        return obj.submitter_email

    def get_time_spent(self, obj):
        return format_time_spent(obj.time_spent)

    def get_row_class(self, obj):
        return obj.get_priority_css_class

    def get_kbitem(self, obj):
        return obj.kbitem.title if obj.kbitem else ""

    def get_extra_data(self, obj):
        return obj.extra_data if obj.extra_data else ""

    def get_paired_count(self, obj):
        return obj.beam_property.count() + obj.beam_taxlot.count()


class ReportTicketSerializer(serializers.ModelSerializer):
    formtype = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()
    first_staff_followup = serializers.SerializerMethodField()
    closed_date = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    time_spent = serializers.SerializerMethodField()
    is_followup_required = serializers.SerializerMethodField()
    number_followups = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    kbitem = serializers.SerializerMethodField()
    merged_to = serializers.SerializerMethodField()
    queue = serializers.SerializerMethodField()
    extra_data = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = ('queue', 'formtype', 'created', 'id', 'title', 'status', 'assigned_to', 'submitter_email',
                  'time_spent', 'description', 'contact_name', 'contact_email', 'building_name', 'building_address',
                  'pm_id', 'kbitem', 'merged_to', 'first_staff_followup', 'closed_date', 'is_followup_required',
                  'number_followups', 'extra_data')

    def get_formtype(self, obj):
        return obj.ticket_form.name

    def get_created(self, obj):
        return datetime.strftime(obj.created, '%m-%d-%Y %H:%M:%S')

    def get_first_staff_followup(self, obj):
        followups = [f for f in FollowUp.objects.filter(ticket_id=obj.id).order_by('date') if is_helpdesk_staff(f.user)]
        return datetime.strftime(followups[0].date, '%m-%d-%Y %H:%M:%S') if followups else 'None'

    def get_closed_date(self, obj):
        terminal_statuses = [Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS, Ticket.DUPLICATE_STATUS]
        if obj.status in terminal_statuses:
            f = FollowUp.objects.filter(ticket_id=obj.id, new_status__in=terminal_statuses).order_by('date').last()
            return datetime.strftime(f.date, '%m-%d-%Y %H:%M:%S') if f else 'None'
        else:
            return 'None'

    def get_assigned_to(self, obj):
        if obj.assigned_to:
            if obj.assigned_to.get_full_name():
                return obj.assigned_to.get_full_name()
            elif obj.assigned_to.email:
                return obj.assigned_to.email
            else:
                return obj.assigned_to.username
        else:
            return 'None'

    def get_time_spent(self, obj):
        return format_time_spent(obj.time_spent)

    def get_is_followup_required(self, obj):
        starting_statuses = [Ticket.OPEN_STATUS, Ticket.REOPENED_STATUS, Ticket.NEW_STATUS]
        return 'Yes' if obj.status in starting_statuses else 'No'

    def get_number_followups(self, obj):
        return FollowUp.objects.filter(ticket_id=obj.id).count()

    def get_status(self, obj):
        return obj.get_status

    def get_kbitem(self, obj):
        return obj.kbitem.title if obj.kbitem else ''

    def get_merged_to(self, obj):
        return obj.merged_to.queue.title + '-' + str(obj.merged_to.id) if obj.merged_to else ''

    def get_queue(self, obj):
        return obj.queue.title

    def get_extra_data(self, obj):
        return obj.extra_data if obj.extra_data else ''
