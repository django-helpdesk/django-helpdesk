from typing import ClassVar

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.mixins import CreateModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from helpdesk import settings as helpdesk_settings
from helpdesk.models import FollowUp, FollowUpAttachment, Ticket
from helpdesk.serializers import (
    FollowUpAttachmentSerializer,
    FollowUpSerializer,
    PublicTicketListingSerializer,
    TicketSerializer,
    UserSerializer,
)
from helpdesk.user import HelpdeskUser


def accessible_tickets(user):
    """The tickets `user` is allowed to reach through the API.

    This mirrors `HelpdeskUser.can_access_ticket()` rather than being merely
    stricter than it. The staff UI grants access through the queue permission
    model and additionally to a ticket assigned to the user, even when that
    ticket sits in a queue they were not granted, so the API has to grant the
    same set or it would deny requests the UI allows.

    With HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION disabled, or for a
    superuser, `get_queues()` returns every queue and this filter is a no-op.
    """
    return Ticket.objects.filter(
        Q(queue__in=HelpdeskUser(user).get_queues()) | Q(assigned_to=user)
    ).distinct()


def restrict_relation(serializer, field_name, queryset):
    """Narrow a writable relation so it cannot reference an unreachable object.

    The querysets below already stop reads and updates, because DRF resolves
    both through `get_queryset()`. Creation is the remaining path: a POST names
    a ticket or a follow-up by primary key, and without this the serializer
    would accept one belonging to a queue the user cannot access.
    """
    target = getattr(serializer, "child", serializer)
    field = target.fields.get(field_name)
    if field is not None and hasattr(field, "queryset"):
        field.queryset = queryset


class ConservativePagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"


class UserTicketViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A list of all the tickets submitted by the current user

    The view is paginated by default
    """

    serializer_class = PublicTicketListingSerializer
    pagination_class = ConservativePagination
    permission_classes: ClassVar[list] = [IsAuthenticated]

    def get_queryset(self):
        tickets = Ticket.objects.filter(
            submitter_email=self.request.user.email
        ).order_by("-created")
        for ticket in tickets:
            ticket.set_custom_field_values()
        return tickets


class TicketViewSet(viewsets.ModelViewSet):
    """
    A viewset that provides the standard actions to handle Ticket

    You can filter the tickets by status using the `status` query parameter. For example:

    `/api/tickets/?status=Open,Resolved` will return all the tickets that are Open or Resolved.
    """

    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    pagination_class = ConservativePagination
    permission_classes: ClassVar[list] = [IsAdminUser]

    def get_queryset(self):
        tickets = accessible_tickets(self.request.user)

        # filter by status
        status = self.request.query_params.get("status", None)
        if status:
            statuses = status.split(",") if status else []
            status_choices = helpdesk_settings.TICKET_STATUS_CHOICES
            number_statuses = []
            for status in statuses:
                for choice in status_choices:
                    if str(choice[0]) == status:
                        number_statuses.append(choice[0])
            if number_statuses:
                tickets = tickets.filter(status__in=number_statuses)

        for ticket in tickets:
            ticket.set_custom_field_values()
        return tickets

    def get_object(self):
        ticket = super().get_object()
        ticket.set_custom_field_values()
        return ticket

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        # Stops a ticket being created in, or moved into, a queue the user was
        # not granted.
        restrict_relation(
            serializer, "queue", HelpdeskUser(self.request.user).get_queues()
        )
        return serializer


class FollowUpViewSet(viewsets.ModelViewSet):
    queryset = FollowUp.objects.all()
    serializer_class = FollowUpSerializer
    pagination_class = ConservativePagination
    permission_classes: ClassVar[list] = [IsAdminUser]

    def get_queryset(self):
        return FollowUp.objects.filter(ticket__in=accessible_tickets(self.request.user))

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        restrict_relation(serializer, "ticket", accessible_tickets(self.request.user))
        return serializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FollowUpAttachmentViewSet(viewsets.ModelViewSet):
    queryset = FollowUpAttachment.objects.all()
    serializer_class = FollowUpAttachmentSerializer
    pagination_class = ConservativePagination
    permission_classes: ClassVar[list] = [IsAdminUser]

    def accessible_followups(self):
        return FollowUp.objects.filter(ticket__in=accessible_tickets(self.request.user))

    def get_queryset(self):
        return FollowUpAttachment.objects.filter(
            followup__in=self.accessible_followups()
        )

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        restrict_relation(serializer, "followup", self.accessible_followups())
        return serializer


class CreateUserView(CreateModelMixin, GenericViewSet):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes: ClassVar[list] = [IsAdminUser]
