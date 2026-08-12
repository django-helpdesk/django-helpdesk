from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from helpdesk.models import (
    FollowUp,
    FollowUpAttachment,
    Queue,
    Ticket,
    TicketChange,
)

from .helpers import get_user


class FollowUpEditTests(TestCase):
    """Editing a follow-up must not cost the ticket its history."""

    def setUp(self):
        self.user = get_user(username="editor", is_staff=True)
        self.client.login(username=self.user.get_username(), password="password")
        self.queue = Queue.objects.create(title="Products", slug="products")
        self.ticket = Ticket.objects.create(
            title="Product not received",
            submitter_email="test@example.com",
            queue=self.queue,
        )
        self.followup = FollowUp.objects.create(
            ticket=self.ticket,
            title="E-Mail Received from test@example.com",
            comment="Original comment",
            date=timezone.now(),
            public=True,
            user=self.user,
            message_id="<abc@example.com>",
        )
        self.url = reverse(
            "helpdesk:followup_edit", args=[self.ticket.id, self.followup.id]
        )

    def _post(self, **overrides):
        data = {
            "ticket": self.ticket.id,
            "title": "Edited title",
            "comment": "Edited comment",
            "public": "on",
            "new_status": "",
            "time_spent": "",
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_edit_applies_the_submitted_values(self):
        response = self._post()

        self.assertRedirects(response, self.ticket.get_absolute_url())
        self.followup.refresh_from_db()
        self.assertEqual(self.followup.title, "Edited title")
        self.assertEqual(self.followup.comment, "Edited comment")

    def test_edit_keeps_the_same_row(self):
        followup_id, date = self.followup.id, self.followup.date

        self._post()

        self.assertEqual(FollowUp.objects.count(), 1)
        followup = FollowUp.objects.get()
        # A new row would break every permalink to this follow-up.
        self.assertEqual(followup.id, followup_id)
        self.assertEqual(followup.date, date)
        self.assertEqual(followup.user, self.user)

    def test_edit_keeps_the_message_id(self):
        self._post()

        self.followup.refresh_from_db()
        self.assertEqual(self.followup.message_id, "<abc@example.com>")

    def test_edit_keeps_the_recorded_ticket_changes(self):
        TicketChange.objects.create(
            followup=self.followup, field="Status", old_value="Open", new_value="Closed"
        )

        self._post()

        self.assertEqual(TicketChange.objects.count(), 1)
        self.assertEqual(TicketChange.objects.get().followup_id, self.followup.id)

    def test_edit_keeps_attachments(self):
        attachment = FollowUpAttachment.objects.create(
            followup=self.followup,
            file=SimpleUploadedFile("notes.txt", b"attached file content"),
            filename="notes.txt",
            mime_type="text/plain",
            size=21,
        )

        self._post()

        attachment.refresh_from_db()
        self.assertEqual(attachment.followup_id, self.followup.id)

    def test_edit_can_reassign_the_followup_to_another_ticket(self):
        other = Ticket.objects.create(
            title="Another ticket",
            submitter_email="test@example.com",
            queue=self.queue,
        )

        self._post(ticket=other.id)

        self.followup.refresh_from_db()
        self.assertEqual(self.followup.ticket, other)
