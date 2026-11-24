from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.forms import EditTicketForm
from helpdesk.models import Queue, Ticket


class StaffEditTicketViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ticket_editor",
            password="testpass123",
            is_staff=True,
        )
        self.queue = Queue.objects.create(
            title="Editing Support",
            slug="editing-support",
        )
        self.ticket = Ticket.objects.create(
            title="Original title",
            submitter_email="original@example.com",
            queue=self.queue,
        )
        self.url = reverse(
            "helpdesk:edit",
            args=[self.ticket.pk],
        )
        self.client.force_login(self.user)

    def test_get_displays_edit_form(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "helpdesk/edit_ticket.html")
        self.assertIsInstance(response.context["form"], EditTicketForm)
        self.assertEqual(response.context["form"].instance, self.ticket)

    def test_invalid_post_does_not_modify_ticket(self):
        response = self.client.post(
            self.url,
            {"title": "", "submitter_email": "invalid-email"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.title, "Original title")

    def test_valid_post_updates_ticket_and_redirects(self):
        response = self.client.post(
            self.url,
            {
                "title": "Updated title",
                "secret_key": self.ticket.secret_key,
                "submitter_email": "updated@example.com",
                "queue": str(self.queue.pk),
                "priority": str(self.ticket.priority),
            },
        )

        self.assertEqual(
            response.status_code,
            302,
            response.context["form"].errors if response.context else "",
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.title, "Updated title")
        self.assertEqual(
            self.ticket.submitter_email,
            "updated@example.com",
        )
