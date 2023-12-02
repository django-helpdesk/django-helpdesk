from django.db.models.signals import post_save
from django.dispatch import receiver
from . import settings

import requests
import requests.exceptions
import logging

from .models import Ticket
from .serializers import TicketSerializer

logger = logging.getLogger(__name__)

def notify_followup_webhooks(followup):
    urls = settings.HELPDESK_GET_FOLLOWUP_WEBHOOK_URLS()
    if not urls:
        return
    # Serialize the ticket associated with the followup
    ticket = followup.ticket
    serialized_ticket = TicketSerializer(ticket).data

    # Prepare the data to send
    data = {
        'ticket': serialized_ticket,
        'queue_slug': ticket.queue.slug,
        'followup_id': followup.id
    }

    for url in urls:
        try:
            requests.post(url, json=data, timeout=settings.HELPDESK_WEBHOOK_TIMEOUT)
        except requests.exceptions.Timeout:
            logger.error('Timeout while sending followup webhook to %s', url)


@receiver(post_save, sender=Ticket)
def ticket_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    urls = settings.HELPDESK_GET_NEW_TICKET_WEBHOOK_URLS()
    if not urls:
        return
    # Serialize the ticket
    serialized_ticket = TicketSerializer(instance).data

    # Prepare the data to send
    data = {
        'ticket': serialized_ticket,
        'queue_slug': instance.queue.slug
    }

    for url in urls:
        try:
            requests.post(url, json=data, timeout=settings.HELPDESK_WEBHOOK_TIMEOUT)
        except requests.exceptions.Timeout:
            logger.error('Timeout while sending new ticket webhook to %s', url)
