from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from helpdesk import settings as helpdesk_settings
from helpdesk.models import PreSetReply, Queue
from helpdesk.user import HelpdeskUser


class RawDetailsPreSetReplyTestCase(TestCase):
    """Checks on the /raw/preset/ endpoint used to prefill the comment box."""

    XSS_BODY = "<script>alert('xss')</script>"

    def setUp(self):
        self.original_per_queue_permission = (
            helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
        )
        helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = True

        User = get_user_model()
        self.queue_allowed = Queue.objects.create(title="Allowed", slug="allowed")
        self.queue_denied = Queue.objects.create(title="Denied", slug="denied")

        self.user = User.objects.create_user(
            username="staff", password="password", email="staff@example.com"
        )
        self.user.is_staff = True
        self.user.save()
        # The 'helpdesk.' prefix must be trimmed to look the permission up
        self.user.user_permissions.add(
            Permission.objects.get(codename=self.queue_allowed.permission_name[9:])
        )

        self.allowed_preset = PreSetReply.objects.create(
            name="Allowed reply", body=self.XSS_BODY
        )
        self.allowed_preset.queues.add(self.queue_allowed)

        self.denied_preset = PreSetReply.objects.create(
            name="Denied reply", body="Secret body"
        )
        self.denied_preset.queues.add(self.queue_denied)

        self.global_preset = PreSetReply.objects.create(
            name="Global reply", body="Anyone may read this"
        )

        # A queue open to public submission is offered by the queue pickers but
        # is not one this user may open.
        self.queue_public = Queue.objects.create(
            title="Public", slug="public", allow_public_submission=True
        )
        self.public_preset = PreSetReply.objects.create(
            name="Public queue reply", body="Secret body"
        )
        self.public_preset.queues.add(self.queue_public)

        self.client = Client()
        self.client.login(username="staff", password="password")

    def tearDown(self):
        helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = (
            self.original_per_queue_permission
        )

    def _get(self, preset):
        return self.client.get(
            reverse("helpdesk:raw", kwargs={"type_": "preset"}), {"id": preset.id}
        )

    def test_body_is_not_served_as_html(self):
        """The stored body is echoed back verbatim, so it must not be HTML."""
        response = self._get(self.allowed_preset)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.content.decode(), self.XSS_BODY)

    def test_preset_of_an_inaccessible_queue_is_not_disclosed(self):
        response = self._get(self.denied_preset)
        self.assertEqual(response.status_code, 404)

    def test_preset_of_a_public_submission_queue_is_not_disclosed(self):
        """Accepting public submissions does not make a queue readable."""
        self.assertFalse(
            HelpdeskUser(self.user).can_access_queue(self.queue_public),
        )
        response = self._get(self.public_preset)
        self.assertEqual(response.status_code, 404)

    def test_preset_of_an_accessible_queue_is_served(self):
        response = self._get(self.allowed_preset)
        self.assertEqual(response.status_code, 200)

    def test_preset_without_queue_is_served(self):
        response = self._get(self.global_preset)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Anyone may read this")

    def test_preset_shared_between_queues_is_served_once(self):
        """A reply attached to several readable queues must not fan out."""
        second_allowed = Queue.objects.create(title="Allowed 2", slug="allowed2")
        self.user.user_permissions.add(
            Permission.objects.get(codename=second_allowed.permission_name[9:])
        )
        self.allowed_preset.queues.add(second_allowed)

        response = self._get(self.allowed_preset)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), self.XSS_BODY)

    def test_unknown_preset_returns_404(self):
        response = self.client.get(
            reverse("helpdesk:raw", kwargs={"type_": "preset"}), {"id": 999999}
        )
        self.assertEqual(response.status_code, 404)

    def test_non_numeric_id_returns_404(self):
        response = self.client.get(
            reverse("helpdesk:raw", kwargs={"type_": "preset"}), {"id": "abc"}
        )
        self.assertEqual(response.status_code, 404)

    def test_every_preset_is_served_without_per_queue_permission(self):
        """Without per queue permissions every staff member reads every reply."""
        helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = False

        for preset in (self.allowed_preset, self.denied_preset, self.global_preset):
            with self.subTest(preset=preset.name):
                self.assertEqual(self._get(preset).status_code, 200)
