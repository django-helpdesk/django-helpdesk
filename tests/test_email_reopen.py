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

    def test_reply_to_missing_ticket_id_creates_new_ticket(self):
        message = EmailMessage()
        message["To"] = "support@example.com"
        message["Message-Id"] = "<missing-ticket@example.com>"

        payload = {
            "body": "Help with a new issue",
            "full_body": "Help with a new issue",
            "subject": "New support request",
            "queue": self.queue,
            "sender_email": "customer@example.com",
            "priority": 3,
        }

        create_object_from_email_message(
            message=message,
            ticket_id=999999,
            payload=payload,
            files=[],
            logger=logging.getLogger("helpdesk"),
        )

        self.assertEqual(
            Ticket.objects.filter(title="New support request").count(),
            1,
        )

    def test_reply_to_merged_ticket_uses_destination_ticket(self):
        destination = Ticket.objects.create(
            title="Destination ticket",
            queue=self.queue,
            submitter_email="customer@example.com",
        )
        self.ticket.merged_to = destination
        self.ticket.save()

        message = EmailMessage()
        message["To"] = "support@example.com"
        message["Message-Id"] = "<merged-reply@example.com>"

        payload = {
            "body": "Additional information",
            "full_body": "Additional information",
            "subject": "Printer on fire",
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

        self.assertTrue(
            FollowUp.objects.filter(
                ticket=destination,
                comment="Additional information",
            ).exists()
        )
        self.assertFalse(
            FollowUp.objects.filter(
                ticket=self.ticket,
                comment="Additional information",
            ).exists()
        )

    def test_attachment_validation_error_preserves_followup(self):
        from django.core.exceptions import ValidationError

        message = EmailMessage()
        message["To"] = "support@example.com"
        message["Message-Id"] = "<invalid-attachment@example.com>"

        payload = {
            "body": "Please check the attachment",
            "full_body": "Please check the attachment",
            "subject": "Printer on fire",
            "queue": self.queue,
            "sender_email": "customer@example.com",
            "priority": 3,
        }

        logger = mock.Mock(spec=logging.Logger)

        with (
            mock.patch.object(helpdesk_settings, "HELPDESK_ENABLE_ATTACHMENTS", True),
            mock.patch(
                "helpdesk.email.process_attachments",
                side_effect=ValidationError("Invalid attachment"),
            ) as process_attachments,
        ):
            create_object_from_email_message(
                message=message,
                ticket_id=self.ticket.id,
                payload=payload,
                files=[],
                logger=logger,
            )

        process_attachments.assert_called_once()
        logger.error.assert_called_once()
        self.assertIn("Invalid attachment", logger.error.call_args.args[0])
        self.assertTrue(
            FollowUp.objects.filter(
                ticket=self.ticket,
                comment="Please check the attachment",
            ).exists()
        )

    def test_followup_created_when_attachments_disabled(self):
        with mock.patch.object(helpdesk_settings, "HELPDESK_ENABLE_ATTACHMENTS", False):
            followup = self.reply()

        self.assertEqual(followup.comment, "Still broken")
        self.assertEqual(followup.ticket_id, self.ticket.id)
