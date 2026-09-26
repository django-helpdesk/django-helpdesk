import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import Permission
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from helpdesk import settings as helpdesk_settings
from helpdesk.models import FollowUp, FollowUpAttachment, Queue, Ticket, TicketChange

from .helpers import get_user


class FollowUpCopyTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.media_root = Path(directory.name)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = get_user(username="copier", is_staff=True)
        self.client.force_login(self.user)
        self.queue = Queue.objects.create(title="Support", slug="support")
        self.source = Ticket.objects.create(title="Original request", queue=self.queue)
        self.target = Ticket.objects.create(title="Related request", queue=self.queue)
        self.followup = FollowUp.objects.create(
            ticket=self.source,
            title="Investigation",
            comment="Restart the device.",
            user=None,
            public=True,
            message_id="<original@example.com>",
            new_status=Ticket.CLOSED_STATUS,
            time_spent=timedelta(minutes=45),
            email_recipients=["customer@example.com"],
        )
        self.url = reverse(
            "helpdesk:followup_copy", args=[self.source.pk, self.followup.pk]
        )

    def post(self, **data):
        return self.client.post(self.url, {"ticket": self.target.pk, **data})

    def test_get_does_not_copy_and_offers_other_open_tickets(self):
        closed = Ticket.objects.create(
            title="Closed", queue=self.queue, status=Ticket.CLOSED_STATUS
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(
            response.context["form"].fields["ticket"].queryset, [self.target]
        )
        self.assertEqual(FollowUp.objects.count(), 1)
        self.assertNotContains(response, f'value="{closed.pk}"')

    def test_copy_keeps_source_and_does_not_replay_history(self):
        TicketChange.objects.create(
            followup=self.followup, field="Status", old_value="Open", new_value="Closed"
        )
        source_date = self.followup.date
        response = self.post()
        copied = self.target.followup_set.get()
        self.assertRedirects(response, copied.get_absolute_url())
        self.followup.refresh_from_db()
        self.assertEqual(self.followup.ticket, self.source)
        self.assertEqual(self.followup.date, source_date)
        self.assertEqual(copied.comment, self.followup.comment)
        self.assertIn(f"#{self.source.pk}", copied.title)
        self.assertEqual(copied.user, self.user)
        self.assertFalse(copied.public)
        self.assertIsNone(copied.message_id)
        self.assertIsNone(copied.new_status)
        self.assertIsNone(copied.time_spent)
        self.assertEqual(copied.email_recipients, [])
        self.assertFalse(copied.ticketchange_set.exists())
        self.assertEqual(len(mail.outbox), 0)
        self.target.refresh_from_db()
        self.assertEqual(self.target.status, Ticket.OPEN_STATUS)

    def test_public_copy_requires_explicit_selection(self):
        self.post(public="on")
        self.assertTrue(self.target.followup_set.get().public)

    def attachment(self, name="notes.txt"):
        return FollowUpAttachment.objects.create(
            followup=self.followup,
            file=SimpleUploadedFile(name, b"investigation notes"),
            filename=name,
            mime_type="text/plain",
            size=19,
        )

    def test_attachments_are_independent_files(self):
        original = self.attachment()
        self.post()
        copied = self.target.followup_set.get().followupattachment_set.get()
        self.assertNotEqual(original.file.name, copied.file.name)
        with copied.file.open("rb") as content:
            self.assertEqual(content.read(), b"investigation notes")
        self.assertEqual(copied.filename, original.filename)
        original.file.delete(save=False)
        self.assertTrue(copied.file.storage.exists(copied.file.name))

    def test_partial_attachment_failure_rolls_back_rows_and_files(self):
        self.attachment("a.txt")
        missing = self.attachment("b.txt")
        missing.file.delete(save=False)
        before = {p for p in self.media_root.rglob("*") if p.is_file()}
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unable to copy the attachments")
        self.assertFalse(self.target.followup_set.exists())
        self.assertEqual(FollowUpAttachment.objects.count(), 2)
        self.assertEqual(before, {p for p in self.media_root.rglob("*") if p.is_file()})

    def test_rejects_self_closed_and_missing_target(self):
        closed = Ticket.objects.create(
            title="Closed", queue=self.queue, status=Ticket.CLOSED_STATUS
        )
        for target in (self.source.pk, closed.pk, 99999, ""):
            with self.subTest(target=target):
                response = self.post(ticket=target)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertEqual(FollowUp.objects.count(), 1)

    def test_followup_must_belong_to_source_ticket(self):
        url = reverse("helpdesk:followup_copy", args=[self.target.pk, self.followup.pk])
        self.assertEqual(
            self.client.post(url, {"ticket": self.source.pk}).status_code, 404
        )

    def test_queue_permissions_apply_to_source_and_target(self):
        other_queue = Queue.objects.create(title="Restricted", slug="restricted")
        forbidden = Ticket.objects.create(title="Secret", queue=other_queue)
        self.user.user_permissions.add(
            Permission.objects.get(codename=self.queue.permission_name.split(".", 1)[1])
        )
        with mock.patch.object(
            helpdesk_settings, "HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION", True
        ):
            response = self.client.get(self.url)
            self.assertNotIn(
                forbidden, response.context["form"].fields["ticket"].queryset
            )
            response = self.post(ticket=forbidden.pk)
            self.assertTrue(response.context["form"].errors)
            self.source.queue = other_queue
            self.source.save()
            self.assertEqual(self.post().status_code, 403)
        self.assertEqual(FollowUp.objects.count(), 1)

    def test_non_staff_and_anonymous_cannot_copy(self):
        self.client.force_login(get_user(username="customer", is_staff=False))
        self.assertIn(self.post().status_code, (302, 403))
        self.client.logout()
        self.assertIn(self.post().status_code, (302, 403))
        self.assertEqual(FollowUp.objects.count(), 1)

    def test_does_not_duplicate_automatically_calculated_time(self):
        with mock.patch.object(helpdesk_settings, "FOLLOWUP_TIME_SPENT_AUTO", True):
            self.post()
        self.assertIsNone(self.target.followup_set.get().time_spent)

    def test_other_http_methods_cannot_copy(self):
        self.assertEqual(self.client.delete(self.url).status_code, 405)
        self.assertEqual(FollowUp.objects.count(), 1)
