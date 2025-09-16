from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from helpdesk.models import Queue, Ticket

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
