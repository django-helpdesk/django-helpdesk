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


@register.filter
def priority_color(priority):
    """
    Display the text corresponding to the state
    """
    css_class = 'alert-'
    if priority == 1:
        css_class += 'danger'
    if priority == 2:
        css_class += 'warning'
    if priority == 3:
        css_class = ''
    if priority == 4:
        css_class += 'info'
    if priority == 5:
        css_class += 'success'
    return css_class
