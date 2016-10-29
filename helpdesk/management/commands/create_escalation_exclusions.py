#!/usr/bin/python
"""
Jutda Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

scripts/create_escalation_exclusion.py - Easy way to routinely add particular
                                         days to the list of days on which no
                                         escalation should take place.
"""
from __future__ import print_function

from datetime import timedelta, date
import getopt
from optparse import make_option
import sys

from django.core.management.base import BaseCommand, CommandError

from helpdesk.models import EscalationExclusion, Queue


class Command(BaseCommand):

    def __init__(self):
        BaseCommand.__init__(self)

        self.option_list += (
            make_option(
                '--days', '-d',
                help='Days of week (monday, tuesday, etc)'),
            make_option(
                '--occurrences', '-o',
                type='int',
                default=1,
                help='Occurrences: How many weeks ahead to exclude this day'),
            make_option(
                '--queues', '-q',
                help='Queues to include (default: all). Use queue slugs'),
            make_option(
                '--escalate-verbosely', '-x',
                action='store_true',
                default=False,
                dest='escalate-verbosely',
                help='Display a list of dates excluded'),
        )

    def handle(self, *args, **options):
        days = options['days']
        # optparse should already handle the `or 1`
        occurrences = options['occurrences'] or 1
        verbose = False
        queue_slugs = options['queues']
        queues = []

        if options['escalate-verbosely']:
            verbose = True

        if not (days and occurrences):
            raise CommandError('One or more occurrences must be specified.')

        if queue_slugs is not None:
            queue_set = queue_slugs.split(',')
            for queue in queue_set:
                try:
                    q = Queue.objects.get(slug__exact=queue)
                except Queue.DoesNotExist:
                    raise CommandError("Queue %s does not exist." % queue)
                queues.append(q)

        create_exclusions(days=days, occurrences=occurrences, verbose=verbose, queues=queues)


day_names = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}


def create_exclusions(days, occurrences, verbose, queues):
    days = days.split(',')
    for day in days:
        day_name = day
        day = day_names[day]
        workdate = date.today()
        i = 0
        while i < occurrences:
            if day == workdate.weekday():
                if EscalationExclusion.objects.filter(date=workdate).count() == 0:
                    esc = EscalationExclusion(name='Auto Exclusion for %s' % day_name, date=workdate)
                    esc.save()

                    if verbose:
                        print("Created exclusion for %s %s" % (day_name, workdate))

                    for q in queues:
                        esc.queues.add(q)
                        if verbose:
                            print("  - for queue %s" % q)

                i += 1
            workdate += timedelta(days=1)


def usage():
    print("Options:")
    print(" --days, -d: Days of week (monday, tuesday, etc)")
    print(" --occurrences, -o: Occurrences: How many weeks ahead to exclude this day")
    print(" --queues, -q: Queues to include (default: all). Use queue slugs")
    print(" --verbose, -v: Display a list of dates excluded")


if __name__ == '__main__':
    # This script can be run from the command-line or via Django's manage.py.
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'd:o:q:v', ['days=', 'occurrences=', 'verbose', 'queues='])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    days = None
    occurrences = 1
    verbose = False
    queue_slugs = None
    queues = []

    for o, a in opts:
        if o in ('-x', '--escalate-verbosely'):
            verbose = True
        if o in ('-d', '--days'):
            days = a
        if o in ('-q', '--queues'):
            queue_slugs = a
        if o in ('-o', '--occurrences'):
            occurrences = int(a) or 1

    if not (days and occurrences):
        usage()
        sys.exit(2)

    if queue_slugs is not None:
        queue_set = queue_slugs.split(',')
        for queue in queue_set:
            try:
                q = Queue.objects.get(slug__exact=queue)
            except Queue.DoesNotExist:
                print("Queue %s does not exist." % queue)
                sys.exit(2)
            queues.append(q)

    create_exclusions(days=days, occurrences=occurrences, verbose=verbose, queues=queues)
