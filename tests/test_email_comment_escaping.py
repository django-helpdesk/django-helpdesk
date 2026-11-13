"""Follow-up comments in the HTML part of notification e-mails."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from helpdesk.models import Queue, Ticket
from helpdesk.update_ticket import update_ticket

User = get_user_model()

SUBMITTER = "submitter@example.com"


def html_part(message):
    (content, mimetype), *_ = message.alternatives
    assert mimetype == "text/html"
    return content


class EmailCommentEscapingTests(TestCase):
    def setUp(self):
        self.queue = Queue.objects.create(title="Queue", slug="queue")
        self.staff = User.objects.create(
            username="staff", email="staff@example.com", is_staff=True
        )
        self.ticket = Ticket.objects.create(
            title="Ticket", queue=self.queue, submitter_email=SUBMITTER
        )
        mail.outbox.clear()

    def add_comment(self, comment):
        update_ticket(self.staff, self.ticket, comment=comment, public=True)
        return next(m for m in mail.outbox if SUBMITTER in m.to)

    def test_should_escape_html_in_comment(self):
        message = self.add_comment('<a href="https://evil.example">click</a>')

        html = html_part(message)
        self.assertNotIn('<a href="https://evil.example">', html)
        self.assertIn("&lt;a href=", html)

    def test_should_escape_comment_once_for_every_recipient(self):
        self.ticket.assigned_to = User.objects.create(
            username="owner", email="owner@example.com"
        )
        self.ticket.save()

        update_ticket(self.staff, self.ticket, comment="a & b", public=True)

        self.assertEqual(len(mail.outbox), 2)
        for message in mail.outbox:
            html = html_part(message)
            self.assertIn("a &amp; b", html, message.to)
            self.assertNotIn("&amp;amp;", html, message.to)

    def test_should_escape_templated_comment_once(self):
        self.ticket.title = "O'Brien & Sons"
        self.ticket.save()

        message = self.add_comment("Re {{ ticket.title }}")

        self.assertEqual(self.ticket.followup_set.last().comment, "Re O'Brien & Sons")
        html = html_part(message)
        self.assertIn("Re O&#x27;Brien &amp; Sons", html)
        self.assertNotIn("&amp;amp;", html)

    def test_should_keep_comment_line_breaks(self):
        message = self.add_comment("line one\r\nline two")

        self.assertIn("line one<br>line two", html_part(message))
