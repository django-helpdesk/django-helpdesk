from django import template
from helpdesk.models import Ticket

register = template.Library()


@register.filter
def status_color(status):
    if status == Ticket.OPEN_STATUS:
        return 'primary'
    if status == Ticket.REOPENED_STATUS:
        return 'info'
    if status == Ticket.RESOLVED_STATUS:
        return 'success'
    if status == Ticket.CLOSED_STATUS:
        return 'default'
    if status == Ticket.DUPLICATE_STATUS:
        return 'warning'
