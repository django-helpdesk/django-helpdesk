# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import migrations
from django.conf import settings
from django.db.utils import IntegrityError
from django.utils.translation import ugettext_lazy as _


def create_and_assign_permissions(apps, schema_editor):
    # If neither Permission nor Membership mechanism are enabled, ignore the migration
    if not ((hasattr(settings, 'HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION') and
            settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION) or
            (hasattr(settings, 'HELPDESK_ENABLE_PER_QUEUE_STAFF_MEMBERSHIP') and
            settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_MEMBERSHIP)):
        return

    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    # Otherwise, two steps:
    #   1. Create the permission for existing Queues
    #   2. Assign the permission to user according to QueueMembership objects

    # First step: prepare the permission for each queue
    Queue = apps.get_model('helpdesk', 'Queue')

    for q in Queue.objects.all():
        if not q.permission_name:
            basename = "queue_access_%s" % q.slug
            q.permission_name = "helpdesk.%s" % basename
        else:
            # Strip the `helpdesk.` prefix
            basename = q.permission_name[9:]

        try:
            Permission.objects.create(
                name=_("Permission for queue: ") + q.title,
                content_type=ContentType.objects.get(model="queue"),
                codename=basename,
            )
        except IntegrityError:
            # Seems that it already existed, safely ignore it
            pass
        q.save()

    # Second step: map the permissions according to QueueMembership
    QueueMembership = apps.get_model('helpdesk', 'QueueMembership')
    for qm in QueueMembership.objects.all():
        user = qm.user
        for q in qm.queues.all():
            # Strip the `helpdesk.` prefix
            p = Permission.objects.get(codename=q.permission_name[9:])
            user.user_permissions.add(p)
        qm.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0008_extra_for_permissions'),
    ]

    operations = [
        migrations.RunPython(create_and_assign_permissions)
    ]
