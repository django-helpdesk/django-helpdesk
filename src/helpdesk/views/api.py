from typing import ClassVar

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from rest_framework import viewsets
from rest_framework.mixins import CreateModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    DjangoModelPermissions,
    IsAdminUser,
    IsAuthenticated,
)
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


def restrict_relation(serializer, field_name, queryset):
    """Narrow a writable relation so it cannot reference an unreachable object.

    The querysets below already stop reads and updates, because DRF resolves
    both through `get_queryset()`. Creation is the remaining path: a POST names
    a ticket or a follow-up by primary key, and without this the serializer
    would accept one belonging to a queue the user cannot access.

    Raises rather than returning quietly when the field is absent or is not a
    relation. Skipping silently would drop an authorization check the moment a
    field is renamed, which is the one failure mode this must not have.
    """
    target = getattr(serializer, "child", serializer)
    field = target.fields.get(field_name)
    if field is None:
        raise ImproperlyConfigured(
            f"{type(target).__name__} has no field {field_name!r} to restrict."
        )
    if not hasattr(field, "queryset"):
        raise ImproperlyConfigured(
            f"{type(target).__name__}.{field_name} is not a relation, "
            "so it cannot be restricted to a queryset."
        )
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
        tickets = HelpdeskUser(self.request.user).accessible_tickets()

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
        # merged_to points at another Ticket, so it is a second way across the
        # boundary: without this a restricted user can link one of their own
        # tickets to a foreign one, which both confirms that ticket exists and
        # writes a reference into it.
        restrict_relation(
            serializer,
            "merged_to",
            HelpdeskUser(self.request.user).accessible_tickets(),
        )
        return serializer


class FollowUpViewSet(viewsets.ModelViewSet):
    queryset = FollowUp.objects.all()
    serializer_class = FollowUpSerializer
    pagination_class = ConservativePagination
    permission_classes: ClassVar[list] = [IsAdminUser]

    def get_queryset(self):
        return FollowUp.objects.filter(
            ticket__in=HelpdeskUser(self.request.user).accessible_tickets()
        )

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        restrict_relation(
            serializer, "ticket", HelpdeskUser(self.request.user).accessible_tickets()
        )
        return serializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FollowUpAttachmentViewSet(viewsets.ModelViewSet):
    queryset = FollowUpAttachment.objects.all()
    serializer_class = FollowUpAttachmentSerializer
    pagination_class = ConservativePagination
    permission_classes: ClassVar[list] = [IsAdminUser]

    def accessible_followups(self):
        return FollowUp.objects.filter(
            ticket__in=HelpdeskUser(self.request.user).accessible_tickets()
        )

    def get_queryset(self):
        return FollowUpAttachment.objects.filter(
            followup__in=self.accessible_followups()
        )

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        restrict_relation(serializer, "followup", self.accessible_followups())
        return serializer


class CreateUserView(CreateModelMixin, GenericViewSet):
    """Create a user account.

    `IsAdminUser` only tests `is_staff`, the flag granting entry to the admin
    site, never the right to create an account. On its own it leaves this
    endpoint more permissive than `/admin/auth/user/add/`, which refuses the
    same request from a staff member lacking `auth.add_user`.

    `DjangoModelPermissions` adds that check. It derives the permission from
    the queryset's model, so a project substituting its own AUTH_USER_MODEL is
    covered without naming `auth.add_user` here. Both classes are required:
    the model permission alone would open the endpoint to any account holding
    it, staff or not.
    """

    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes: ClassVar[list] = [IsAdminUser, DjangoModelPermissions]
