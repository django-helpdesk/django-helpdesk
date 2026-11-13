"""HTML rendering of ticket text (comment, resolution, description) in emails."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from helpdesk import settings as helpdesk_settings
from helpdesk.models import Queue, Ticket
from helpdesk.update_ticket import update_ticket

User = get_user_model()

SUBMITTER = "submitter@example.com"


def html_part(message):
    (content, mimetype), *_ = message.alternatives
    assert mimetype == "text/html"
    return content


class EmailHtmlRenderingTestBase(TestCase):
    def setUp(self):
        self.queue = Queue.objects.create(title="Queue", slug="queue")
        self.staff = User.objects.create(
            username="staff", email="staff@example.com", is_staff=True
        )
        self.ticket = Ticket.objects.create(
            title="Ticket",
            queue=self.queue,
            submitter_email=SUBMITTER,
            description="Hello\n\nThe data is in `/srv/data`.",
        )
        mail.outbox.clear()

    def submitter_email(self):
        return next(m for m in mail.outbox if SUBMITTER in m.to)

    def add_comment(self, comment, **kwargs):
        update_ticket(self.staff, self.ticket, comment=comment, public=True, **kwargs)
        return self.submitter_email()

    def resolve(self, resolution):
        return self.add_comment(resolution, new_status=Ticket.RESOLVED_STATUS)


class EmailHtmlWithoutMarkdownTests(EmailHtmlRenderingTestBase):
    def test_should_keep_comment_line_breaks_when_setting_disabled(self):
        message = self.add_comment("line one\r\nline two")

        self.assertIn("line one<br>line two", html_part(message))


RESOLUTION = """Copied to `/srv/new`.

```
line one
line two
```

Kind regards"""


@mock.patch.object(helpdesk_settings, "HELPDESK_EMAIL_RENDER_MARKDOWN", True)
class EmailHtmlWithMarkdownTests(EmailHtmlRenderingTestBase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create(username="owner", email="owner@example.com")
        self.ticket.assigned_to = self.owner
        self.ticket.save()

    def owner_email(self):
        return next(m for m in mail.outbox if self.owner.email in m.to)

    def test_should_render_resolution_markdown_for_submitter_when_setting_enabled(
        self,
    ):
        html = html_part(self.resolve(RESOLUTION))

        self.assertIn("<code>/srv/new</code>", html)
        self.assertIn("<pre><code>line one", html)
        self.assertIn("<p>Kind regards</p>", html)

    def test_should_render_ticket_resolution_markdown_for_owner_when_setting_enabled(
        self,
    ):
        self.resolve(RESOLUTION)

        html = html_part(self.owner_email())
        self.assertIn("<code>/srv/new</code>", html)
        self.assertIn("<pre><code>line one", html)

    def test_should_render_comment_markdown_when_setting_enabled(self):
        html = html_part(self.add_comment("Some **bold** text"))

        self.assertIn("<strong>bold</strong>", html)

    def test_should_render_description_markdown_when_setting_enabled(self):
        self.add_comment("A comment")

        html = html_part(self.owner_email())
        self.assertIn("<p>Hello</p>", html)
        self.assertIn("<code>/srv/data</code>", html)

    def test_should_not_add_br_inside_code_block_when_template_uses_linebreaksbr(
        self,
    ):
        self.ticket.description = RESOLUTION
        self.ticket.save()

        self.add_comment("A comment")

        # updated_owner renders {{ ticket.description|linebreaksbr }}
        html = html_part(self.owner_email())
        self.assertIn("line one&#10;line two", html)
        self.assertNotIn("line one<br>", html)
        self.assertNotIn("</p><br>", html)

    def test_should_keep_raw_markdown_in_text_part_when_setting_enabled(self):
        message = self.resolve(RESOLUTION)

        self.assertIn("Copied to `/srv/new`.", message.body)
        self.assertIn("```\nline one\nline two\n```", message.body)
        self.assertNotIn("<code>", message.body)

    def test_should_strip_script_and_unsafe_links_when_rendering_markdown(self):
        html = html_part(
            self.add_comment("<script>alert(1)</script> [x](javascript:alert(1))")
        )

        self.assertNotIn("<script>", html)
        self.assertNotIn("javascript:", html)

    def test_should_render_markdown_for_every_recipient_when_setting_enabled(self):
        self.add_comment("Some **bold** text")

        self.assertEqual(len(mail.outbox), 2)
        for message in mail.outbox:
            self.assertIn("<strong>bold</strong>", html_part(message), message.to)

    def test_should_leave_markdown_unrendered_when_setting_disabled(self):
        with mock.patch.object(
            helpdesk_settings, "HELPDESK_EMAIL_RENDER_MARKDOWN", False
        ):
            html = html_part(self.resolve("Some **bold** text"))

        self.assertIn("Some **bold** text", html)
        self.assertNotIn("<strong>", html)

    def test_should_strip_remote_images_when_rendering_markdown(self):
        html = html_part(self.add_comment("![pixel](https://tracker.example/p.gif)"))

        self.assertNotIn("<img", html)
        self.assertNotIn("tracker.example", html)
