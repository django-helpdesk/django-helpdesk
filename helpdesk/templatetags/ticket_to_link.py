"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

templatetags/ticket_to_link.py - Used in ticket comments to allow wiki-style
                                 linking to other tickets. Including text such
                                 as '#3180' in a comment automatically links
                                 that text to ticket number 3180, with styling
                                 to show the status of that ticket (eg a closed
                                 ticket would have a strikethrough).
"""

import re

from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe

from helpdesk.models import Ticket


def num_to_link(text):
    """ Display a link to ticket when finding #ID (eg: " #31 " and 31 matches a ticket ID) """
    if text == '':
        return text

    matches = []
    for match in re.finditer(r"(?:[^&]|\b|^)#(\d+)\b", text):
        matches.append(match)

    for match in reversed(matches):
        number = match.groups()[0]
        url = reverse('helpdesk:view', args=[number])
        try:
            ticket = Ticket.objects.get(id=number)
        except Ticket.DoesNotExist:
            ticket = None

        if ticket:
            style = 'text-'
            if ticket.status == Ticket.CLOSED_STATUS:
                style += 'line-through'
            elif ticket.status == Ticket.OPEN_STATUS:
                style += 'info'
            elif ticket.status == Ticket.REOPENED_STATUS:
                style += 'warning'
            elif ticket.status == Ticket.RESOLVED_STATUS:
                style += 'success'
            elif ticket.status == Ticket.DUPLICATE_STATUS:
                style += 'danger'
            text = "%s <a href='%s' class='%s' data-toggle='tooltip' title='%s'>#%s</a>%s" % (
                text[:match.start() + 1],
                url,
                style,
                '%s (%s)' % (ticket.title, ticket.get_status_display()),
                match.groups()[0],
                text[match.end():]
            )
    return mark_safe(text)


register = template.Library()
register.filter(num_to_link)
