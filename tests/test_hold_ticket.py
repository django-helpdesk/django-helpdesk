from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import FollowUp, Queue, Ticket, TicketChange


class HoldTicketTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="hold-ticket-staff",
            is_staff=True,
        )
        self.queue = Queue.objects.create(
            title="Hold Test Queue",
            slug="hold-test",
        )
        self.ticket = Ticket.objects.create(
            queue=self.queue,
            title="Hold test ticket",
            description="Test hold and unhold actions",
        )
        self.client.force_login(self.staff)

    def test_hold_ticket_records_change(self):
        response = self.client.get(reverse("helpdesk:hold", args=[self.ticket.pk]))

        self.assertRedirects(response, self.ticket.get_absolute_url())
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.on_hold)

        followup = FollowUp.objects.get(ticket=self.ticket)
        self.assertEqual(followup.title, "Ticket placed on hold")
        self.assertTrue(followup.public)
        self.assertEqual(followup.user, self.staff)

        change = TicketChange.objects.get(followup=followup)
        self.assertEqual(change.old_value, "False")
        self.assertEqual(change.new_value, "True")

    def test_unhold_ticket_records_change(self):
        self.ticket.on_hold = True
        self.ticket.save()

        response = self.client.get(reverse("helpdesk:unhold", args=[self.ticket.pk]))

        self.assertRedirects(response, self.ticket.get_absolute_url())
        self.ticket.refresh_from_db()
        self.assertFalse(self.ticket.on_hold)

        followup = FollowUp.objects.get(ticket=self.ticket)
        self.assertEqual(followup.title, "Ticket taken off hold")
        self.assertTrue(followup.public)

        change = TicketChange.objects.get(followup=followup)
        self.assertEqual(change.old_value, "True")
        self.assertEqual(change.new_value, "False")
