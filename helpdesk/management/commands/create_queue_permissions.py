#!/usr/bin/python
"""
scripts/create_queue_permissions.py -
    Create automatically permissions for all Queues.

    This is rarely needed. However, one use case is the scenario where the
    slugs of the Queues have been changed, and thus the Permission should be
    recreated according to the new slugs.

    No cleanup of permissions is performed.

    It should be safe to call this script multiple times or with partial
    existing permissions.
"""

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from django.utils.translation import gettext_lazy as _
from helpdesk.models import Queue


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
            help='Display a list of dates excluded'
        )

    def handle(self, *args, **options):
        queue_slugs = options['queues']

        if queue_slugs is not None:
            queues = Queue.objects.filter(slug__in=queue_slugs)
        else:
            queues = Queue.objects.all()

        # Create permissions for the queues, which may be all or not
        for q in queues:
            self.stdout.write(f"Preparing Queue {q} [{q.slug}]")

            if q.permission_name:
                self.stdout.write(
                    f"  .. already has `permission_name={q.permission_name}`")
                basename = q.permission_name[9:]
            else:
                basename = q.generate_permission_name()
                self.stdout.write(
                    f"  .. generated `permission_name={q.permission_name}`")
                q.save()

            self.stdout.write(
                f"  .. checking permission codename `{basename}`")

            try:
                Permission.objects.create(
                    name=_("Permission for queue: ") + q.title,
                    content_type=ContentType.objects.get(model="queue"),
                    codename=basename,
                )
            except IntegrityError:
                self.stdout.write("  .. permission already existed, skipping")
