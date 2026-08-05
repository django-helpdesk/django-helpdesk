"""
The sanitized preview that gives staff back a readable rendering of an HTML
email without serving the sender's markup from the helpdesk origin.

What matters here is that all three layers described in helpdesk.sanitize are
actually present on the response, not just the sanitizer: the first one is a
blocklist race we should expect to lose eventually, the other two are what make
losing it survivable.
"""

import logging

from django.test import TestCase, override_settings
from django.urls import reverse

from helpdesk.email import extract_email_metadata
from helpdesk.models import FollowUpAttachment, Queue, Ticket

from .helpers import get_staff_user, get_user

logger = logging.getLogger("helpdesk")

PAYLOAD = (
    "<html><body>"
    "<p style='color:red'>Dear customer</p>"
    "<table><tr><td>Invoice</td><td>42 EUR</td></tr></table>"
    "<a href='https://example.com/ok'>legitimate link</a>"
    "<a href='javascript:alert(1)'>bad link</a>"
    "<div onmouseover='alert(1)'>hover me</div>"
    "<script>alert(document.cookie)</script>"
    "<iframe src='//evil.example'></iframe>"
    "</body></html>"
)


def build_email(html_body):
    from email.message import EmailMessage

    message = EmailMessage()
    message["Subject"] = "Formatted email"
    message["From"] = "customer@example.com"
    message["To"] = "helpdesk@example.com"
    message.set_content("plain text body")
    message.add_alternative(html_body, subtype="html")
    return message.as_string()


class HTMLPreviewTestCase(TestCase):
    def setUp(self):
        self.queue = Queue.objects.create(
            title="Email queue",
            slug="mail",
            email_address="helpdesk@example.com",
            allow_email_submission=True,
        )
        extract_email_metadata(build_email(PAYLOAD), self.queue, logger=logger)
        self.ticket = Ticket.objects.get()
        self.attachment = FollowUpAttachment.objects.get()
        self.user = get_staff_user()
        self.client.login(username=self.user.username, password="password")

    def preview_url(self, ticket=None, attachment=None):
        return reverse(
            "helpdesk:attachment_preview",
            args=[(ticket or self.ticket).id, (attachment or self.attachment).id],
        )

    def test_stored_file_stays_inert_while_mime_type_records_the_truth(self):
        """The extension governs what the web server serves, the mime_type only
        records what the bytes are and drives the preview."""
        self.assertTrue(self.attachment.file.name.endswith(".txt"))
        self.assertEqual(self.attachment.mime_type, "text/html")

    def test_preview_strips_everything_executable(self):
        response = self.client.get(self.preview_url())
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertNotIn("<script", body.lower())
        self.assertNotIn("onmouseover", body.lower())
        self.assertNotIn("javascript:", body.lower())
        self.assertNotIn("<iframe", body.lower())

    def test_preview_keeps_the_message_readable(self):
        """The whole point of the feature: a non-technical reader still gets
        their formatted email."""
        body = self.client.get(self.preview_url()).content.decode("utf-8")
        self.assertIn("Dear customer", body)
        self.assertIn("42 EUR", body)
        self.assertIn("<table", body)
        self.assertIn("color:red", body)
        self.assertIn("https://example.com/ok", body)

    def test_preview_is_sandboxed_and_locked_down(self):
        """Sanitizing is the layer most likely to fail, so assert the two that
        hold even when it does."""
        response = self.client.get(self.preview_url())
        csp = response["Content-Security-Policy"]
        self.assertIn("default-src 'none'", csp)
        self.assertIn("sandbox", csp)
        self.assertIn("img-src 'none'", csp)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")

    @override_settings(HELPDESK_HTML_PREVIEW_ALLOW_REMOTE_IMAGES=True)
    def test_remote_images_can_be_opted_into(self):
        # The setting is read at import time by helpdesk.settings, so reload the
        # module the way the project's other settings tests do.
        from importlib import reload

        from helpdesk import sanitize
        from helpdesk import settings as helpdesk_settings

        reload(helpdesk_settings)
        reload(sanitize)
        try:
            self.assertIn("img-src https: http:", sanitize.preview_csp())
        finally:
            reload(helpdesk_settings)
            reload(sanitize)

    def test_preview_refuses_non_html_attachments(self):
        self.attachment.mime_type = "application/pdf"
        self.attachment.save()
        response = self.client.get(self.preview_url())
        self.assertEqual(response.status_code, 404)

    def test_preview_requires_staff(self):
        self.client.logout()
        response = self.client.get(self.preview_url())
        self.assertNotEqual(response.status_code, 200)

    def test_preview_enforces_queue_permissions(self):
        """Going through a view is what makes this check possible at all: the
        raw media link never had one.

        Only meaningful with per-queue permissions turned on, since by default
        any staff member has full access to every queue.
        """
        from helpdesk import settings as helpdesk_settings

        original = helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
        helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = True
        try:
            get_user(username="outsider", is_staff=True)
            self.client.logout()
            self.client.login(username="outsider", password="password")
            response = self.client.get(self.preview_url())
            self.assertIn(response.status_code, (403, 404))
        finally:
            helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = original

    def test_attachment_id_must_belong_to_the_ticket(self):
        other_ticket = Ticket.objects.create(
            title="Unrelated", queue=self.queue, description="x"
        )
        response = self.client.get(self.preview_url(ticket=other_ticket))
        self.assertEqual(response.status_code, 404)
