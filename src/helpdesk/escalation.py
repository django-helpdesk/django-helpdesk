"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

escalation.py - Escalation rules shared by the nightly management command
                and the staff views.
"""

from django.utils import timezone
from django.utils.translation import gettext as _

from helpdesk.lib import safe_template_context
from helpdesk.models import Ticket


def escalatable_tickets(queryset):
    """Return the tickets in `queryset` that are eligible for escalation."""
    return queryset.filter(
        status__in=Ticket.OPEN_STATUSES,
        priority__gt=1,
        queue__escalate_days__isnull=False,
    ).exclude(queue__escalate_days=0)


def can_escalate(ticket):
    """Whether this ticket is eligible for escalation."""
    return escalatable_tickets(Ticket.objects.filter(pk=ticket.pk)).exists()


def escalate_ticket(ticket, user=None, comment=None):
    """Raise the ticket's priority by one and notify everyone involved.
    Returns the FollowUp created."""
    old_priority = ticket.priority
    ticket.last_escalation = timezone.now()
    ticket.priority -= 1
    ticket.save()

    context = safe_template_context(ticket)

    sent_to = set()
    ticket.send(
        {
            "submitter": ("escalated_submitter", context),
            "ticket_cc": ("escalated_cc", context),
            "assigned_to": ("escalated_owner", context),
        },
        sent_to=sent_to,
        fail_silently=True,
    )

    followup = ticket.followup_set.create(
        title=_("Ticket Escalated"),
        public=True,
        user=user,
        email_recipients=sorted(sent_to),
        comment=comment if comment is not None else _("Ticket escalated manually"),
    )

    followup.ticketchange_set.create(
        field=_("Priority"),
        old_value=old_priority,
        new_value=ticket.priority,
    )

    return followup
