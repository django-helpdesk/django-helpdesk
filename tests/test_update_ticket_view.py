from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import CustomField, Queue, Ticket

User = get_user_model()


class UpdateTicketViewTests(TestCase):
    def setUp(self):
        self.queue = Queue.objects.create(title="Test Queue", slug="test")
        self.user = User.objects.create_user(
            username="testuser", password="pass123", is_staff=True
        )

        # Create a sample ticket
        self.ticket = Ticket.objects.create(
            title="Sample ticket", queue=self.queue, submitter_email="test@example.com"
        )

    def test_redirect_after_login_does_not_crash(self):
        """If unauthenticated user tries to update a ticket, they should
        be redirected to login, and after login, no crash should occur.
        """
        url = reverse("helpdesk:update", kwargs={"ticket_id": self.ticket.id})

        # Try to access update page without login
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # redirect to login

        # Log in
        self.client.login(username="testuser", password="pass123")

        # Try accessing again (simulating redirect after login)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sample ticket")


class UpdateTicketCustomFieldsTests(TestCase):
    def setUp(self):
        self.queue = Queue.objects.create(title="Test Queue", slug="test")
        self.user = User.objects.create_user(
            username="testuser",
            password="pass123",
            is_staff=True,
        )

        self.ticket = Ticket.objects.create(
            title="Sample ticket", queue=self.queue, submitter_email="test@example.com"
        )

        self.custom_field = CustomField.objects.create(
            name="extra_info",
            label="Extra Info",
            data_type="varchar",
            max_length=50,
            required=False,
        )

    def test_custom_field_persists_after_invalid_post(self):
        """Custom fields should still be shown after form validation errors."""

        url = reverse("helpdesk:update", kwargs={"ticket_id": self.ticket.id})

        self.client.login(username="testuser", password="pass123")

        response = self.client.get(url)
        self.assertContains(response, "Extra Info")

        response = self.client.post(
            url,
            {
                "queue": self.queue.id,
                # "title" missing
                "body": "Test body",
                "priority": 3,
                # custom prefix is from CustomFieldMixin
                "custom_extra_info": "My custom text",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "There are errors in the form")
        self.assertContains(response, "Extra Info")
        self.assertContains(response, "My custom text")
