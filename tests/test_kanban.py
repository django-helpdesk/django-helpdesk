from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from helpdesk import settings as helpdesk_settings
from helpdesk.models import Queue, Ticket

from .helpers import get_staff_user


def _make_queue():
    return Queue.objects.create(title="Test Queue", slug="test_kanban")


def _ticket(queue, status, modified_weeks_ago):
    t = Ticket.objects.create(
        title="Test ticket",
        queue=queue,
        status=status,
        due_date=timezone.now() + timedelta(weeks=1),
    )
    # Ticket.save() overwrites modified; bypass it to set the age we want
    Ticket.objects.filter(pk=t.pk).update(
        modified=timezone.now() - timedelta(weeks=modified_weeks_ago)
    )
    return t


class KanbanClosedTicketFilterTests(TestCase):
    def setUp(self):
        self.queue = _make_queue()
        self.user = get_staff_user()
        self.client.login(username=self.user.get_username(), password="password")
        self.url = reverse("helpdesk:kanban")

    def test_recent_closed_ticket_is_shown(self):
        """
        Tests HELPDESK_KANBAN_DEFAULT_RENDER_CLOSED_TICKETS_WEEKS
        Check if ticket modified within 2 weeks does show
        as it should. (2 < 6)
        """
        t = _ticket(self.queue, Ticket.CLOSED_STATUS, modified_weeks_ago=2)
        with mock.patch.object(
            helpdesk_settings, "HELPDESK_KANBAN_DEFAULT_RENDER_CLOSED_TICKETS_WEEKS", 6
        ):
            response = self.client.get(self.url)
        self.assertContains(response, t.title)

    def test_stale_closed_ticket_is_hidden(self):
        """
        Tests HELPDESK_KANBAN_DEFAULT_RENDER_CLOSED_TICKETS_WEEKS
        Check if closed ticket modified 8 weeks ago doesn't show
        as it should. (8 > 6)
        """
        t = _ticket(self.queue, Ticket.CLOSED_STATUS, modified_weeks_ago=8)
        with mock.patch.object(
            helpdesk_settings, "HELPDESK_KANBAN_DEFAULT_RENDER_CLOSED_TICKETS_WEEKS", 6
        ):
            response = self.client.get(self.url)
        self.assertNotContains(response, t.title)

    def test_stale_duplicate_ticket_is_hidden(self):
        """
        Tests HELPDESK_KANBAN_DEFAULT_RENDER_CLOSED_TICKETS_WEEKS
        Check if duplicate ticket modified 8 weeks ago doesn't show
        as it should. (8 > 6)
        """
        t = _ticket(self.queue, Ticket.DUPLICATE_STATUS, modified_weeks_ago=8)
        with mock.patch.object(
            helpdesk_settings, "HELPDESK_KANBAN_DEFAULT_RENDER_CLOSED_TICKETS_WEEKS", 6
        ):
            response = self.client.get(self.url)
        self.assertNotContains(response, t.title)

    def test_disabled_filter_shows_stale_closed_ticket(self):
        """
        Tests HELPDESK_KANBAN_DEFAULT_RENDER_CLOSED_TICKETS_WEEKS
        All tickets show when this setting is disabled (0).
        """
        t = _ticket(self.queue, Ticket.CLOSED_STATUS, modified_weeks_ago=8)
        with mock.patch.object(
            helpdesk_settings, "HELPDESK_KANBAN_DEFAULT_RENDER_CLOSED_TICKETS_WEEKS", 0
        ):
            response = self.client.get(self.url)
        self.assertContains(response, t.title)
