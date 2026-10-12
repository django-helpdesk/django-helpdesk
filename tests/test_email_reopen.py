import logging
from email.message import EmailMessage
from unittest import mock

from django.test import TestCase

from helpdesk import settings as helpdesk_settings
from helpdesk.email import create_object_from_email_message
from helpdesk.models import FollowUp, Queue, Ticket


class EmailReopenTests(TestCase):
    def setUp(self):
        self.queue = Queue.objects.create(title="Support", slug="support")
        self.ticket = Ticket.objects.create(
            title="Printer on fire",
            queue=self.queue,
            submitter_email="customer@example.com",
        )

    def reply(self, **headers):
        message = EmailMessage()
        message["To"] = "support@example.com"
        message["Message-Id"] = "<reply@example.com>"
        for name, value in headers.items():
            message[name] = value
        payload = {
            "body": "Still broken",
            "full_body": "Still broken",
            "subject": f"[support-{self.ticket.id}] Printer on fire",
            "queue": self.queue,
            "sender_email": "customer@example.com",
            "priority": 3,
        }
        create_object_from_email_message(
            message=message,
            ticket_id=self.ticket.id,
            payload=payload,
            files=[],
            logger=logging.getLogger("helpdesk"),
        )
        self.ticket.refresh_from_db()
        return FollowUp.objects.get(ticket=self.ticket)

    def set_status(self, status):
        self.ticket.status = status
        self.ticket.save()

    def test_should_reopen_closed_ticket_when_reply_received(self):
        self.set_status(Ticket.CLOSED_STATUS)

        followup = self.reply()

        self.assertEqual(self.ticket.status, Ticket.REOPENED_STATUS)
        self.assertEqual(followup.new_status, Ticket.REOPENED_STATUS)

    def test_should_leave_resolved_ticket_resolved_when_reply_received_by_default(
        self,
    ):
        self.set_status(Ticket.RESOLVED_STATUS)

        followup = self.reply()

        self.assertEqual(self.ticket.status, Ticket.RESOLVED_STATUS)
        self.assertIsNone(followup.new_status)

    def test_should_reopen_resolved_ticket_when_status_is_in_reopen_setting(self):
        self.set_status(Ticket.RESOLVED_STATUS)
        with mock.patch.object(
            helpdesk_settings,
            "EMAIL_REOPEN_STATUSES",
            (Ticket.CLOSED_STATUS, Ticket.RESOLVED_STATUS),
        ):
            followup = self.reply()

        self.assertEqual(self.ticket.status, Ticket.REOPENED_STATUS)
        self.assertEqual(followup.new_status, Ticket.REOPENED_STATUS)

    def test_should_not_reopen_ticket_when_reply_is_an_autoreply(self):
        self.set_status(Ticket.CLOSED_STATUS)

        followup = self.reply(**{"Auto-Submitted": "auto-replied"})

        self.assertEqual(self.ticket.status, Ticket.CLOSED_STATUS)
        self.assertIsNone(followup.new_status)
        self.assertEqual(followup.comment, "Still broken")
