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
            '--days',
            '-d',
            help='Days of week (monday, tuesday, etc) separated by comas'
        )
        parser.add_argument(
            '--occurrences',
            '-o',
            type=int,
            default=1,
            help='Occurrences: How many weeks ahead to exclude this day'
        )
        parser.add_argument(
            '--queues',
            '-q',
            help='Queues to include (default: all). Use queue slugs and separate them with a coma'
        )
        parser.add_argument(
            '--escalate-verbosely',
            '-x',
            action='store_true',
            default=False,
            dest='escalate-verbosely',
            help='Display a list of dates excluded'
        )

    def handle(self, *args, **options):
        days = options['days']
        occurrences = options['occurrences']
        queue_slugs = options['queues']

        verbose = False
        if options['escalate-verbosely']:
            verbose = True

        if not (days and occurrences):
            raise CommandError('One or more occurrences must be specified.')

        queues = []
        if queue_slugs is not None:
            queue_set = queue_slugs.split(',')
            for queue in queue_set:
                try:
                    q = Queue.objects.get(slug__exact=queue)
                except Queue.DoesNotExist:
                    raise CommandError(f"Queue {queue} does not exist.")
                queues.append(q)
        else:
            queues = list(Queue.objects.all())

        self.create_exclusions(
            days=days,
            occurrences=occurrences,
            verbose=verbose,
            queues=queues
        )

    def create_exclusions(self, days, occurrences, verbose, queues):
        days = days.split(',')
        for day in days:
            day_name = day
            day = day_names[day]
            workdate = date.today()
            i = 0
            while i < occurrences:
                if day == workdate.weekday():
                    if not EscalationExclusion.objects.filter(date=workdate).exists():
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
