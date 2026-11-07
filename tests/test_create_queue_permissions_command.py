from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase

from helpdesk.models import Queue


class CreateQueuePermissionsCommandTests(TestCase):
    def test_recreates_permission_when_name_is_missing(self):
        queue = Queue.objects.create(title="Support", slug="support")
        Permission.objects.filter(codename="queue_access_support").delete()
        queue.permission_name = None
        queue.save(update_fields=["permission_name"])

        call_command("create_queue_permissions", queues=[queue.slug])

        queue.refresh_from_db()
        self.assertEqual(queue.permission_name, "helpdesk.queue_access_support")
        self.assertTrue(
            Permission.objects.filter(codename="queue_access_support").exists()
        )
