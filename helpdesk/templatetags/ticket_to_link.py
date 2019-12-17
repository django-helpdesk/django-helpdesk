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
from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe

from helpdesk.models import Ticket

import re


def num_to_link(text):
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
            style = ticket.get_status_display()
            text = "%s <a href='%s' class='ticket_link_status ticket_link_status_%s'>#%s</a>%s" % (
                text[:match.start() + 1], url, style, match.groups()[0], text[match.end():])
    return mark_safe(text)


register = template.Library()
register.filter(num_to_link)
