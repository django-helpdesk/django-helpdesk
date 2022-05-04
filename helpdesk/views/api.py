from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import CreateModelMixin
from django.contrib.auth import get_user_model

from helpdesk.models import Ticket
from helpdesk.serializers import TicketSerializer, UserSerializer


class TicketViewSet(viewsets.ModelViewSet):
    """
    A viewset that provides the standard actions to handle Ticket
    """
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        tickets = Ticket.objects.all()
        for ticket in tickets:
            ticket.set_custom_field_values()
        return tickets

    def get_object(self):
        ticket = super().get_object()
        ticket.set_custom_field_values()
        return ticket


class CreateUserView(CreateModelMixin, GenericViewSet):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
