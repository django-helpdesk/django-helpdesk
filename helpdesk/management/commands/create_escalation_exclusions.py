#!/usr/bin/python
"""
Jutda Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

scripts/create_escalation_exclusion.py - Easy way to routinely add particular
                                         days to the list of days on which no
                                         escalation should take place.
"""

from datetime import date, timedelta
from django.core.management.base import BaseCommand, CommandError
from helpdesk.models import EscalationExclusion, Queue

day_names = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '-d',
            '--days',
            nargs='*',
            choices=list(day_names.keys()),
            required=True,
            help='Days of week (monday, tuesday, etc). Enter the days as space separated list.'
        )
        parser.add_argument(
            '-o',
            '--occurrences',
            default=1,
            type=int,
            help='Occurrences: How many weeks ahead to exclude this day'
        )
        parser.add_argument(
            '-q',
            '--queues',
            nargs='*',
            choices=list(Queue.objects.values_list('slug', flat=True)),
            help='Queues to include (default: all). Enter the queues slug as space separated list.'
        )
        parser.add_argument(
            '-x',
            '--exclude-verbosely',
            action='store_true',
            default=False,
            help='Display a list of dates excluded'
        )

    def handle(self, *args, **options):
        days = options['days']
        occurrences = options['occurrences']
        verbose = options['exclude_verbosely']
        queue_slugs = options['queues']

        if not (days and occurrences):
            raise CommandError('One or more occurrences must be specified.')

        queues = []
        if queue_slugs is not None:
            queues = Queue.objects.filter(slug__in=queue_slugs)

        for day_name in days:
            day = day_names[day_name]
            workdate = date.today()
            i = 0
            while i < occurrences:
                if day == workdate.weekday():
                    if EscalationExclusion.objects.filter(date=workdate).count() == 0:
                        esc = EscalationExclusion.objects.create(
                            name=f'Auto Exclusion for {day_name}',
                            date=workdate
                        )

                        if verbose:
                            self.stdout.write(f"Created exclusion for {day_name} {workdate}")

                        for q in queues:
                            esc.queues.add(q)
                            if verbose:
                                self.stdout.write(f"  - for queue {q}")

                    i += 1
                workdate += timedelta(days=1)
