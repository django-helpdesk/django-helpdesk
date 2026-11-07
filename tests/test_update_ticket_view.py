from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.sites.models import Site
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from helpdesk import settings as helpdesk_settings
from helpdesk.models import CustomField, FollowUp, Queue, Ticket

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


class PublicUpdateTicketTests(TestCase):
    """The comment form on the public ticket page posts to helpdesk:update
    with the ticket's secret key and the submitter's email, and no login."""

    def setUp(self):
        self.queue = Queue.objects.create(title="Test Queue", slug="test")
        self.ticket = Ticket.objects.create(
            title="Sample ticket", queue=self.queue, submitter_email="test@example.com"
        )
        self.url = reverse("helpdesk:update", kwargs={"ticket_id": self.ticket.id})

    def post(self, client=None, **data):
        payload = {"key": self.ticket.secret_key, "mail": "test@example.com"}
        payload.update(data)
        payload = {k: v for k, v in payload.items() if v is not None}
        return (client or self.client).post(self.url, payload)

    def set_status(self, status):
        self.ticket.status = status
        self.ticket.save()

    def followups(self):
        return FollowUp.objects.filter(ticket=self.ticket)

    def public_page_url(self):
        return self.ticket.ticket_url

    def test_submitter_adds_public_comment(self):
        response = self.post(mail="Test@Example.com", comment="More details")
        self.assertRedirects(
            response, self.public_page_url(), fetch_redirect_response=False
        )
        followup = self.followups().get()
        self.assertEqual(followup.comment, "More details")
        self.assertTrue(followup.public)
        self.assertIsNone(followup.user)

    def test_redirect_stays_on_the_requested_host(self):
        # Email links are built from the Sites framework domain, which need not
        # be the host being browsed ("example.com" by default).
        site = Site.objects.get_current()
        site.domain = "mail-links.example.org"
        site.save()
        response = self.post(comment="Hello")
        self.assertTrue(response["Location"].startswith("/"), response["Location"])
        self.assertEqual(self.client.get(response["Location"]).status_code, 200)

    def test_logged_in_submitter_needs_no_key(self):
        # ViewTicket lets a logged-in submitter in without the key, and then
        # renders the form with an empty key.
        User.objects.create_user("submitter", "test@example.com", "pass123")
        self.client.login(username="submitter", password="pass123")
        self.post(key="", comment="Hello")
        self.assertEqual(self.followups().count(), 1)

    def test_wrong_credentials_redirect_to_login(self):
        assignee = User.objects.create_user("assignee", "a@example.com", "pass123")
        self.ticket.assigned_to = assignee
        self.ticket.save()
        cases = [
            ("wrong key", None, {"key": "wrong"}),
            ("empty key", None, {"key": ""}),
            ("wrong email", None, {"mail": "someone@example.com"}),
            ("assignee with wrong key", "assignee", {"key": "wrong"}),
        ]
        for name, username, data in cases:
            with self.subTest(name):
                self.client.logout()
                if username:
                    self.client.login(username=username, password="pass123")
                response = self.post(comment="Hello", **data)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("helpdesk:login"), response["Location"])
        self.assertFalse(self.followups().exists())

    def test_staff_and_requests_without_email_use_the_staff_view(self):
        User.objects.create_user("staff", password="pass123", is_staff=True)
        with mock.patch(
            "helpdesk.views.public.update_ticket_from_public_view"
        ) as public_view:
            self.post(mail=None, comment="Hello")
            self.client.login(username="staff", password="pass123")
            self.post(comment="Hello")
        public_view.assert_not_called()

    def test_public_view_protections_apply(self):
        with self.subTest("CSRF"):
            client = Client(enforce_csrf_checks=True)
            self.assertEqual(self.post(client=client, comment="Hi").status_code, 403)
        with (
            self.subTest("HELPDESK_ANON_ACCESS_RAISES_404"),
            mock.patch.object(
                helpdesk_settings, "HELPDESK_ANON_ACCESS_RAISES_404", True
            ),
        ):
            self.assertEqual(self.post(comment="Hi").status_code, 404)
        self.assertFalse(self.followups().exists())

    def test_staff_fields_are_ignored(self):
        other_queue = Queue.objects.create(title="Other", slug="other")
        self.post(
            comment="Hello",
            title="Changed title",
            priority="1",
            queue=str(other_queue.id),
            public="0",
        )
        self.ticket.refresh_from_db()
        self.assertEqual(
            (self.ticket.title, self.ticket.priority, self.ticket.queue),
            ("Sample ticket", 3, self.queue),
        )
        self.assertTrue(self.followups().get().public)

    def test_status_changes_offered_by_the_page(self):
        open_, resolved = Ticket.OPEN_STATUS, Ticket.RESOLVED_STATUS
        cases = [
            # The page offers no status choice for an open ticket.
            (open_, resolved, open_),
            (resolved, Ticket.REOPENED_STATUS, Ticket.REOPENED_STATUS),
            (resolved, Ticket.CLOSED_STATUS, Ticket.CLOSED_STATUS),
            # Not in the default flow from Resolved.
            (resolved, Ticket.DUPLICATE_STATUS, resolved),
            (resolved, "not-a-number", resolved),
        ]
        for start, requested, expected in cases:
            with self.subTest(start=start, requested=requested):
                self.set_status(start)
                self.post(comment="Hello", new_status=str(requested))
                self.ticket.refresh_from_db()
                self.assertEqual(self.ticket.status, expected)

    def test_status_is_kept_while_dependencies_are_open(self):
        self.set_status(Ticket.REOPENED_STATUS)
        blocker = Ticket.objects.create(title="Blocker", queue=self.queue)
        self.ticket.ticketdependency.create(depends_on=blocker)
        self.post(comment="Done?", new_status=str(Ticket.RESOLVED_STATUS))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.REOPENED_STATUS)

    def test_attachments(self):
        self.post(attachment=SimpleUploadedFile("note.txt", b"hi", "text/plain"))
        attachment = self.followups().get().followupattachment_set.get()
        self.assertEqual(attachment.filename, "note.txt")
        with mock.patch.object(helpdesk_settings, "HELPDESK_ENABLE_ATTACHMENTS", False):
            self.post(
                comment="Hello",
                attachment=SimpleUploadedFile("other.txt", b"hi", "text/plain"),
            )
        self.assertEqual(self.followups().count(), 2)
        self.assertFalse(self.followups().last().followupattachment_set.exists())

    def test_rejected_attachment_rolls_back_the_whole_update(self):
        cases = {
            "disallowed extension": [
                SimpleUploadedFile("note.txt", b"hi", "text/plain"),
                SimpleUploadedFile("page.html", b"<script></script>", "text/html"),
            ],
            # Passes the extension check, fails FollowUpAttachment.full_clean().
            "invalid metadata": [
                SimpleUploadedFile("note.txt", b"hi", "text/" + "x" * 300),
            ],
        }
        for name, files in cases.items():
            with self.subTest(name):
                self.set_status(Ticket.RESOLVED_STATUS)
                response = self.post(
                    comment="See attached",
                    attachment=files,
                    new_status=str(Ticket.CLOSED_STATUS),
                )
                self.assertRedirects(
                    response, self.public_page_url(), fetch_redirect_response=False
                )
                self.ticket.refresh_from_db()
                self.assertEqual(self.ticket.status, Ticket.RESOLVED_STATUS)
                self.assertTrue(list(get_messages(response.wsgi_request)))
        self.assertFalse(self.followups().exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_empty_post_adds_nothing(self):
        self.post(comment="   ")
        self.assertFalse(self.followups().exists())
