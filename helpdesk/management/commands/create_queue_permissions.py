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

from optparse import make_option

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db.utils import IntegrityError
from django.utils.translation import ugettext_lazy as _

from helpdesk.models import Queue


class Command(BaseCommand):

    def __init__(self):
        BaseCommand.__init__(self)

        self.option_list += (
            make_option(
                '--queues', '-q',
                help='Queues to include (default: all). Use queue slugs'),
        )

    def handle(self, *args, **options):
        queue_slugs = options['queues']
        queues = []

        if queue_slugs is not None:
            queue_set = queue_slugs.split(',')
            for queue in queue_set:
                try:
                    q = Queue.objects.get(slug__exact=queue)
                except Queue.DoesNotExist:
                    raise CommandError("Queue %s does not exist." % queue)
                queues.append(q)
        else:
            queues = list(Queue.objects.all())

        # Create permissions for the queues, which may be all or not
        for q in queues:
            self.stdout.write("Preparing Queue %s [%s]" % (q.title, q.slug))

            if q.permission_name:
                self.stdout.write("  .. already has `permission_name=%s`" % q.permission_name)
                basename = q.permission_name[9:]
            else:
                basename = q.generate_permission_name()
                self.stdout.write("  .. generated `permission_name=%s`" % q.permission_name)
                q.save()

            self.stdout.write("  .. checking permission codename `%s`" % basename)

            try:
                Permission.objects.create(
                    name=_("Permission for queue: ") + q.title,
                    content_type=ContentType.objects.get(model="queue"),
                    codename=basename,
                )
            except IntegrityError:
                self.stdout.write("  .. permission already existed, skipping")
