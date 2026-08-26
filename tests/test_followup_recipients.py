import logging

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from helpdesk import settings as helpdesk_settings
from helpdesk.email import extract_email_metadata
from helpdesk.models import EmailTemplate, FollowUp, Queue, Ticket, TicketCC
from helpdesk.update_ticket import update_ticket

User = get_user_model()


class FollowUpRecipientsTests(TestCase):
    """``FollowUp.email_recipients`` records who was actually notified."""

    def setUp(self):
        self.queue = Queue.objects.create(
            title="Products",
            slug="products",
            email_address="products@example.com",
            updated_ticket_cc="queuecc@example.com",
            enable_notifications_on_email_events=True,
        )
        self.staff_user = User.objects.create_user(
            username="staffuser",
            password="testpass123",
            email="staff@example.com",
            is_staff=True,
        )
        self.ticket = Ticket.objects.create(
            title="Product not received",
            submitter_email="submitter@example.com",
            queue=self.queue,
            status=Ticket.OPEN_STATUS,
        )
        TicketCC.objects.create(ticket=self.ticket, email="watcher@example.com")
        mail.outbox.clear()

    def test_public_update_records_everyone_that_was_mailed(self):
        followup = update_ticket(
            user=self.staff_user,
            ticket=self.ticket,
            comment="Your order shipped today.",
            public=True,
        )

        self.assertEqual(
            followup.email_recipients,
            sorted({address for message in mail.outbox for address in message.to}),
        )
        self.assertEqual(
            followup.email_recipients,
            ["queuecc@example.com", "submitter@example.com", "watcher@example.com"],
        )

    def test_acting_user_and_queue_address_are_not_recorded(self):
        followup = update_ticket(
            user=self.staff_user,
            ticket=self.ticket,
            comment="Your order shipped today.",
            public=True,
        )

        self.assertNotIn(self.staff_user.email, followup.email_recipients)
        self.assertNotIn(self.queue.email_address, followup.email_recipients)

    def test_update_that_mails_nobody_records_an_empty_list(self):
        original = helpdesk_settings.HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS
        helpdesk_settings.HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS = True
        try:
            followup = update_ticket(
                user=self.staff_user,
                ticket=self.ticket,
                comment="Internal note.",
                public=False,
            )
        finally:
            helpdesk_settings.HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS = original

        self.assertEqual(mail.outbox, [])
        self.assertEqual(followup.email_recipients, [])

    def test_followup_created_outside_a_mail_path_records_nothing(self):
        followup = FollowUp.objects.create(ticket=self.ticket, title="Manual note")

        self.assertIsNone(followup.email_recipients)

    def test_undeliverable_address_is_not_recorded(self):
        EmailTemplate.objects.filter(template_name="updated_submitter").delete()

        followup = update_ticket(
            user=self.staff_user,
            ticket=self.ticket,
            comment="Your order shipped today.",
            public=True,
        )

        self.assertNotIn("submitter@example.com", followup.email_recipients)
        self.assertIn("watcher@example.com", followup.email_recipients)

    def test_inbound_reply_records_who_the_acknowledgement_went_to(self):
        message = (
            f"To: {self.queue.email_address}\n"
            "From: submitter@example.com\n"
            f"Subject: [products-{self.ticket.id}] Product not received\n"
            "\n"
            "Any news?\n"
        )

        extract_email_metadata(message, self.queue, logging.getLogger("helpdesk"))

        followup = self.ticket.followup_set.latest("date")
        self.assertEqual(
            followup.email_recipients,
            sorted({address for message in mail.outbox for address in message.to}),
        )
        self.assertIn("submitter@example.com", followup.email_recipients)


class FollowUpRecipientsDisplayTests(TestCase):
    """The recipient line is rendered for staff and withheld from the public."""

    def setUp(self):
        self.queue = Queue.objects.create(
            title="Products",
            slug="products",
            email_address="products@example.com",
            allow_public_submission=True,
        )
        self.staff_user = User.objects.create_user(
            username="staffuser",
            password="testpass123",
            email="staff@example.com",
            is_staff=True,
        )
        self.ticket = Ticket.objects.create(
            title="Product not received",
            submitter_email="submitter@example.com",
            queue=self.queue,
            status=Ticket.OPEN_STATUS,
        )
        self.client.login(username="staffuser", password="testpass123")

    def _staff_page(self):
        return self.client.get(reverse("helpdesk:view", args=[self.ticket.id]))

    def test_recorded_recipients_are_listed(self):
        FollowUp.objects.create(
            ticket=self.ticket,
            title="Replied",
            public=True,
            email_recipients=["submitter@example.com", "watcher@example.com"],
        )

        self.assertContains(
            self._staff_page(),
            "Emailed: submitter@example.com, watcher@example.com",
        )

    def test_empty_recipients_say_so_explicitly(self):
        FollowUp.objects.create(
            ticket=self.ticket, title="Internal note", email_recipients=[]
        )

        self.assertContains(self._staff_page(), "Emailed: no one")

    def test_unrecorded_recipients_render_nothing(self):
        FollowUp.objects.create(ticket=self.ticket, title="Legacy follow-up")

        response = self._staff_page()
        self.assertNotContains(response, "Emailed:")
        self.assertNotContains(response, "Emailed: no one")

    def test_public_view_never_lists_recipients(self):
        FollowUp.objects.create(
            ticket=self.ticket,
            title="Replied",
            public=True,
            email_recipients=["submitter@example.com"],
        )

        response = self.client.get(
            reverse("helpdesk:public_view"),
            {
                "ticket": self.ticket.ticket_for_url,
                "email": self.ticket.submitter_email,
                "key": self.ticket.secret_key,
            },
        )
        self.assertTemplateUsed(response, "helpdesk/public_view_ticket.html")
        self.assertNotContains(response, "Emailed:")
