#!/usr/bin/python
"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

scripts/escalate_tickets.py - Easy way to escalate tickets based on their age,
                              designed to be run from Cron or similar.
"""

from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from helpdesk.lib import safe_template_context
from helpdesk.models import EscalationExclusion, Queue, Ticket


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '-q',
            '--queues',
            nargs='*',
            choices=list(Queue.objects.values_list('slug', flat=True)),
            help='Queues to include (default: all). Enter the queues slug as space separated list.'
        )
        parser.add_argument(
            '-x',
            '--escalate-verbosely',
            action='store_true',
            default=False,
            help='Display escalated tickets'
        )

    def handle(self, *args, **options):
        verbose = options['escalate_verbosely']

        queue_slugs = options['queues']
        # Only include queues with escalation configured
        queues = Queue.objects.filter(escalate_days__isnull=False).exclude(escalate_days=0)
        if queue_slugs is not None:
            queues = queues.filter(slug__in=queue_slugs)

        if verbose:
            self.stdout.write(f"Processing: {queues}")

        for queue in queues:
            last = date.today() - timedelta(days=queue.escalate_days)
            today = date.today()
            workdate = last

            days = 0

            while workdate < today:
                if not EscalationExclusion.objects.filter(date=workdate).exists():
                    days += 1
                workdate = workdate + timedelta(days=1)

            req_last_escl_date = timezone.now() - timedelta(days=days)

            for ticket in queue.ticket_set.filter(
                status__in=Ticket.OPEN_STATUSES
            ).exclude(
                priority=1
            ).filter(
                Q(on_hold__isnull=True) | Q(on_hold=False)
            ).filter(
                Q(last_escalation__lte=req_last_escl_date) |
                Q(last_escalation__isnull=True, created__lte=req_last_escl_date)
            ):

                ticket.last_escalation = timezone.now()
                ticket.priority -= 1
                ticket.save()

                context = safe_template_context(ticket)

                ticket.send(
                    {'submitter': ('escalated_submitter', context),
                     'ticket_cc': ('escalated_cc', context),
                     'assigned_to': ('escalated_owner', context)},
                    fail_silently=True,
                )

                if verbose:
                    self.stdout.write(f"  - Esclating {ticket.ticket} from {ticket.priority + 1}>{ticket.priority}")

                followup = ticket.followup_set.create(
                    title=_('Ticket Escalated'),
                    public=True,
                    comment=_('Ticket escalated after %(nb)s days') % {'nb': queue.escalate_days},
                )

                followup.ticketchange_set.create(
                    field=_('Priority'),
                    old_value=ticket.priority + 1,
                    new_value=ticket.priority,
                )
