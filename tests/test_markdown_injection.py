"""Rendered markdown must reach the page without gaining event handlers.

On Django 6.0 and later urlize no longer breaks this payload, so only a run on
Django 5.2 fails without the fix.
"""

from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import FollowUp, Queue, Ticket

# Turns into an onerror attribute if urlize runs over the rendered HTML.
PAYLOAD = '![x](![y" onerror=alert(document.cookie)//](https://example.com/))'


class EventHandlerCollector(HTMLParser):
    """Collects on* attributes as a browser would parse them."""

    def __init__(self):
        super().__init__()
        self.handlers = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name.startswith("on"):
                self.handlers.append((tag, name, value))


class MarkdownInjectionTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create(
            username="staff", is_staff=True, is_superuser=True
        )
        self.user.set_password("pass")
        self.user.save()
        self.queue = Queue.objects.create(title="Queue", slug="queue")
        self.client.login(username="staff", password="pass")

    def handlers_on_ticket_page(self, ticket):
        response = self.client.get(
            reverse("helpdesk:view", kwargs={"ticket_id": ticket.id})
        )
        self.assertEqual(response.status_code, 200)
        collector = EventHandlerCollector()
        collector.feed(response.content.decode())
        return collector.handlers

    def test_description_cannot_inject_an_event_handler(self):
        ticket = Ticket.objects.create(title="t", queue=self.queue, description=PAYLOAD)
        self.assertEqual(self.handlers_on_ticket_page(ticket), [])

    def test_resolution_cannot_inject_an_event_handler(self):
        ticket = Ticket.objects.create(
            title="t",
            queue=self.queue,
            description="d",
            resolution=PAYLOAD,
            status=Ticket.RESOLVED_STATUS,
        )
        self.assertEqual(self.handlers_on_ticket_page(ticket), [])

    def test_followup_comment_cannot_inject_an_event_handler(self):
        ticket = Ticket.objects.create(title="t", queue=self.queue, description="d")
        FollowUp.objects.create(ticket=ticket, title="f", comment=PAYLOAD)
        self.assertEqual(self.handlers_on_ticket_page(ticket), [])

    def test_a_plain_url_is_still_rendered_as_a_link(self):
        ticket = Ticket.objects.create(
            title="t", queue=self.queue, description="see <https://example.com/x>"
        )
        response = self.client.get(
            reverse("helpdesk:view", kwargs={"ticket_id": ticket.id})
        )
        self.assertContains(response, 'href="https://example.com/x"')
