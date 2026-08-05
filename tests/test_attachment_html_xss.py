"""
Attachments come from unauthenticated third parties: anyone can email a queue
or use the public ticket form. They are linked straight from the ticket page and
served inline by the web server, which derives the content type from the file
extension, so an attachment stored as .html executes its own markup and script
in the browser of the staff member who opens it while triaging the ticket.

Two things keep that shut, and both are tested here:
  * the inbound email HTML body is stored as .txt / text/plain
  * .htm and .html are not on the default extension allowlist
"""

import logging

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from helpdesk import settings as helpdesk_settings
from helpdesk.email import HTML_EMAIL_ATTACHMENT_FILENAME, extract_email_metadata
from helpdesk.models import FollowUpAttachment, Queue, Ticket
from helpdesk.validators import validate_file_extension

PAYLOAD = "<script>alert(document.cookie)</script>"
logger = logging.getLogger("helpdesk")


def build_email(sender, recipient, subject, html_body, attachment=None):
    """A multipart/alternative email, optionally carrying a named attachment."""
    from email.message import EmailMessage

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content("plain text body")
    message.add_alternative(html_body, subtype="html")
    if attachment is not None:
        filename, content, (maintype, subtype) = attachment
        message.add_attachment(
            content.encode("utf-8"),
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )
    return message.as_string()


class ExtensionAllowlistTestCase(TestCase):
    def test_html_extensions_are_not_allowed_by_default(self):
        for name in ("payload.html", "payload.htm", "payload.HTML", "payload.HtMl"):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_file_extension(SimpleUploadedFile(name, b"x"))

    def test_default_allowlist_has_no_html(self):
        allowed = {e.lower() for e in helpdesk_settings.HELPDESK_VALID_EXTENSIONS}
        self.assertNotIn(".htm", allowed)
        self.assertNotIn(".html", allowed)

    def test_ordinary_extensions_still_allowed(self):
        for name in ("notes.txt", "scan.pdf", "photo.jpg", "report.docx"):
            with self.subTest(name=name):
                validate_file_extension(SimpleUploadedFile(name, b"x"))


class PublicFormAttachmentTestCase(TestCase):
    """The public ticket form is the shortest path to a stored attachment: no
    email infrastructure and no account needed."""

    def setUp(self):
        self.queue = Queue.objects.create(
            title="Public queue",
            slug="pub",
            allow_public_submission=True,
        )

    def submit(self, filename):
        return self.client.post(
            reverse("helpdesk:home"),
            {
                "queue": self.queue.id,
                "title": "Ticket with attachment",
                "body": "see attachment",
                "submitter_email": "anon@example.com",
                "priority": 3,
                "attachment": SimpleUploadedFile(
                    filename, PAYLOAD.encode("utf-8"), content_type="text/html"
                ),
            },
        )

    def test_anonymous_user_cannot_attach_html(self):
        response = self.submit("payload.html")
        self.assertEqual(response.status_code, 200)  # form redisplayed, not a redirect
        self.assertFalse(FollowUpAttachment.objects.exists())
        self.assertFalse(Ticket.objects.exists())

    def test_anonymous_user_can_still_attach_a_text_file(self):
        response = self.submit("notes.txt")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(FollowUpAttachment.objects.count(), 1)


class InboundEmailAttachmentTestCase(TestCase):
    def setUp(self):
        self.queue = Queue.objects.create(
            title="Email queue",
            slug="mail",
            email_address="helpdesk@example.com",
            allow_email_submission=True,
        )

    def test_html_body_is_stored_as_plain_text(self):
        extract_email_metadata(
            build_email(
                "attacker@example.com",
                "helpdesk@example.com",
                "HTML body",
                f"<html><body><p>Hi</p>{PAYLOAD}</body></html>",
            ),
            self.queue,
            logger=logger,
        )
        attachment = FollowUpAttachment.objects.get()
        self.assertEqual(attachment.filename, HTML_EMAIL_ATTACHMENT_FILENAME)
        self.assertTrue(attachment.filename.endswith(".txt"))
        # The stored extension is what the web server keys off, so that is what
        # has to be inert. mime_type is only a record of what the bytes are, and
        # what the sanitized preview keys off.
        self.assertFalse(attachment.file.name.lower().endswith((".htm", ".html")))
        self.assertEqual(attachment.mime_type, "text/html")
        # The body is kept verbatim, it just is not served as markup any more.
        attachment.file.open("rb")
        content = attachment.file.read().decode("utf-8")
        attachment.file.close()
        self.assertIn(PAYLOAD, content)

    def test_html_named_mime_attachment_is_dropped_but_ticket_survives(self):
        """A sender naming their own part "resume.html" must not get it stored,
        and that rejection must not cost us the ticket or the other parts."""
        extract_email_metadata(
            build_email(
                "attacker@example.com",
                "helpdesk@example.com",
                "Named attachment",
                "<html><body>hello</body></html>",
                attachment=("resume.html", PAYLOAD, ("text", "html")),
            ),
            self.queue,
            logger=logger,
        )
        self.assertEqual(Ticket.objects.count(), 1)
        stored = {a.filename for a in FollowUpAttachment.objects.all()}
        self.assertNotIn("resume.html", stored)
        self.assertFalse(any(n.lower().endswith((".htm", ".html")) for n in stored))
        # The auto-generated body attachment is still there.
        self.assertIn(HTML_EMAIL_ATTACHMENT_FILENAME, stored)
