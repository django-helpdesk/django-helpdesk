#!/usr/bin/python
"""
Jutda Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

scripts/get_email.py - Designed to be run from cron, this script checks the
                       POP and IMAP boxes, or a local mailbox directory,
                       defined for the queues within a
                       helpdesk, creating tickets from the new messages (or
                       adding to existing tickets if needed)
"""
from django.core.management.base import BaseCommand
from helpdesk.email import process_email


class Command(BaseCommand):

    help = 'Process django-helpdesk queues and process e-mails via POP3/IMAP or ' \
           'from a local mailbox directory as required, feeding them into the helpdesk.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--quiet',
            action='store_true',
            dest='quiet',
            default=False,
            help='Hide details about each queue/message as they are processed',
        )
        parser.add_argument(
            '--debug_to_stdout',
            action='store_true',
            dest='debug_to_stdout',
            default=False,
            help='Log additional messaging to stdout.',
        )

    def handle(self, *args, **options):
        quiet = options.get('quiet')
        debug_to_stdout = options.get('debug_to_stdout')
        process_email(quiet=quiet, debug_to_stdout=debug_to_stdout)


if __name__ == '__main__':
    process_email()
