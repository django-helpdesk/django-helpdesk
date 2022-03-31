from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from helpdesk.models import Ticket
from helpdesk.serializers import TicketSerializer


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

