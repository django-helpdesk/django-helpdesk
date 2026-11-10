from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from helpdesk.models import EscalationExclusion, Queue, Ticket


class EscalateTicketsCommandTests(TestCase):
    def test_disabled_escalation_does_not_change_ticket(self):
        queue = Queue.objects.create(title="Support", slug="support", escalate_days=0)
        ticket = Ticket.objects.create(
            queue=queue,
            title="Support request",
            submitter_email="customer@example.com",
        )

        call_command("escalate_tickets")

        ticket.refresh_from_db()
        self.assertEqual(ticket.priority, 3)
        self.assertIsNone(ticket.last_escalation)
        self.assertFalse(ticket.followup_set.exists())

    @patch("helpdesk.models.Ticket.send")
    def test_overdue_ticket_is_escalated(self, mock_send):

        queue = Queue.objects.create(
            title="Escalation Support",
            slug="escalation-support",
            escalate_days=1,
        )
        ticket = Ticket.objects.create(
            queue=queue,
            title="Overdue request",
            submitter_email="customer@example.com",
        )
        Ticket.objects.filter(pk=ticket.pk).update(
            created=timezone.now() - timedelta(days=5)
        )

        call_command("escalate_tickets", queues=[queue.slug], escalate_verbosely=True)

        ticket.refresh_from_db()
        self.assertEqual(ticket.priority, 2)
        self.assertIsNotNone(ticket.last_escalation)
        self.assertEqual(ticket.followup_set.count(), 1)
        mock_send.assert_called_once()

    @patch("helpdesk.models.Ticket.send")
    def test_notify_only_escalates_without_creating_followup(self, mock_send):

        queue = Queue.objects.create(
            title="Notify Support",
            slug="notify-support",
            escalate_days=1,
        )
        ticket = Ticket.objects.create(
            queue=queue,
            title="Notify request",
            submitter_email="customer@example.com",
        )
        Ticket.objects.filter(pk=ticket.pk).update(
            created=timezone.now() - timedelta(days=5)
        )

        call_command(
            "escalate_tickets",
            queues=[queue.slug],
            notify_only=True,
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.priority, 2)
        self.assertIsNotNone(ticket.last_escalation)
        self.assertFalse(ticket.followup_set.exists())
        mock_send.assert_called_once()

    @patch("helpdesk.models.Ticket.send")
    def test_excluded_date_is_not_counted_for_escalation(self, mock_send):

        queue = Queue.objects.create(
            title="Holiday Support",
            slug="holiday-support",
            escalate_days=2,
        )
        ticket = Ticket.objects.create(
            queue=queue,
            title="Holiday request",
            submitter_email="customer@example.com",
        )
        Ticket.objects.filter(pk=ticket.pk).update(
            created=timezone.now() - timedelta(days=1)
        )
        call_command("escalate_tickets", queues=[queue.slug])
        ticket.refresh_from_db()
        self.assertEqual(ticket.priority, 3)
        mock_send.assert_not_called()

        EscalationExclusion.objects.create(
            name="Holiday", date=timezone.localdate() - timedelta(days=1)
        )

        call_command("escalate_tickets", queues=[queue.slug])

        ticket.refresh_from_db()
        self.assertEqual(ticket.priority, 2)
        self.assertEqual(ticket.followup_set.count(), 1)
        mock_send.assert_called_once()
