from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from helpdesk.models import Queue, Ticket
from helpdesk.update_ticket import update_ticket

User = get_user_model()


class PrivateFollowUpCCNotificationTests(TestCase):
    def setUp(self):
        queue = Queue.objects.create(
            title="Support",
            slug="support",
            updated_ticket_cc="staff-list@helpdesk.example",
            enable_notifications_on_email_events=True,
        )
        self.ticket = Ticket.objects.create(
            title="Refund", queue=queue, submitter_email="customer@example.com"
        )
        self.ticket.ticketcc_set.create(email="colleague@example.com")
        customer_user = User.objects.create_user(
            "customer2", email="customer2@example.com"
        )
        self.ticket.ticketcc_set.create(user=customer_user)
        watcher = User.objects.create_user(
            "watcher", email="watcher@helpdesk.example", is_staff=True
        )
        self.ticket.ticketcc_set.create(user=watcher)
        self.agent = User.objects.create_superuser(
            "agent", "agent@helpdesk.example", "pass"
        )

    def notified(self):
        return {address for message in mail.outbox for address in message.to}

    def test_private_followup_only_reaches_staff_ccs(self):
        update_ticket(self.agent, self.ticket, comment="Internal note", public=False)

        self.assertEqual(
            self.notified(),
            {"staff-list@helpdesk.example", "watcher@helpdesk.example"},
        )

    def test_public_followup_still_reaches_every_cc(self):
        update_ticket(self.agent, self.ticket, comment="Good news", public=True)

        self.assertLessEqual(
            {
                "colleague@example.com",
                "customer2@example.com",
                "watcher@helpdesk.example",
            },
            self.notified(),
        )
