from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.humanize.templatetags import humanize
from rest_framework.exceptions import ValidationError

from .forms import TicketForm
from .models import Ticket, CustomField
from .lib import format_time_spent
from .user import HelpdeskUser


class DatatablesTicketSerializer(serializers.ModelSerializer):
    """
    A serializer for the Ticket model, returns data in the format as required by
    datatables for ticket_list.html. Called from staff.datatables_ticket_list.
    """
    ticket = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    submitter = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    row_class = serializers.SerializerMethodField()
    time_spent = serializers.SerializerMethodField()
    queue = serializers.SerializerMethodField()
    kbitem = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        # fields = '__all__'
        fields = ('ticket', 'id', 'priority', 'title', 'queue', 'status',
                  'created', 'due_date', 'assigned_to', 'submitter', 'row_class',
                  'time_spent', 'kbitem')

    def get_queue(self, obj):
        return {"title": obj.queue.title, "id": obj.queue.id}

    def get_ticket(self, obj):
        return str(obj.id) + " " + obj.ticket

    def get_status(self, obj):
        return obj.get_status

    def get_created(self, obj):
        return humanize.naturaltime(obj.created)

    def get_due_date(self, obj):
        return humanize.naturaltime(obj.due_date)

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


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = (
            'id', 'queue', 'title', 'description', 'resolution', 'submitter_email', 'assigned_to', 'status', 'on_hold',
            'priority', 'due_date', 'merged_to'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add custom fields
        for field in CustomField.objects.all():
            self.fields['custom_%s' % field.name] = field.build_api_field()

    def create(self, validated_data):
        """ Use TicketForm to validate and create ticket """
        queues = HelpdeskUser(self.context['request'].user).get_queues()
        queue_choices = [(q.id, q.title) for q in queues]
        data = validated_data.copy()
        data['body'] = data['description']
        # TicketForm needs id for ForeignKey (not the instance themselves)
        data['queue'] = data['queue'].id
        if data.get('assigned_to'):
            data['assigned_to'] = data['assigned_to'].id
        if data.get('merged_to'):
            data['merged_to'] = data['merged_to'].id

        ticket_form = TicketForm(data=data, queue_choices=queue_choices)
        if ticket_form.is_valid():
            ticket = ticket_form.save(user=self.context['request'].user)
            ticket.set_custom_field_values()
            return ticket

        raise ValidationError(ticket_form.errors)

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        instance.save_custom_field_values(validated_data)
        return instance


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'password')

    def create(self, validated_data):
        user = super(UserSerializer, self).create(validated_data)
        user.is_active = True
        user.set_password(validated_data['password'])
        user.save()
        return user
