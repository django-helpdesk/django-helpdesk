from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import Queue, Ticket
from helpdesk.query import query_to_base64

User = get_user_model()


class TicketBadgeClassModelTests(TestCase):
    """The badge CSS class must be keyed by the stable status/priority id,
    never by the displayed (localized) label."""

    def setUp(self):
        self.queue = Queue.objects.create(title="Test Q", slug="test")
        self.ticket = Ticket.objects.create(
            title="Test ticket", submitter_email="a@example.com", queue=self.queue
        )

    def test_status_badge_class_defaults(self):
        expected = {
            Ticket.OPEN_STATUS: "danger",
            Ticket.REOPENED_STATUS: "warning",
            Ticket.RESOLVED_STATUS: "success",
            Ticket.CLOSED_STATUS: "success",
            Ticket.DUPLICATE_STATUS: "secondary",
        }
        for status, css_class in expected.items():
            self.ticket.status = status
            self.assertEqual(self.ticket.get_status_badge_class, css_class)

    def test_priority_badge_class_defaults(self):
        expected = {
            1: "danger",
            2: "warning",
            3: "success",
            4: "info",
            5: "secondary",
        }
        for priority, css_class in expected.items():
            self.ticket.priority = priority
            self.assertEqual(self.ticket.get_priority_badge_class, css_class)

    def test_status_badge_class_unknown_status_falls_back(self):
        self.ticket.status = 99
        self.assertEqual(self.ticket.get_status_badge_class, "")

    def test_status_badge_class_not_keyed_by_displayed_label(self):
        # Renaming the label (e.g. Closed -> Completed) or translating it must
        # not change the color: the class comes from the status id.
        self.ticket.status = Ticket.CLOSED_STATUS
        with patch.object(self.ticket, "get_status_display", return_value="Completed"):
            self.assertEqual(self.ticket.get_status_badge_class, "success")

    @patch.object(
        Ticket,
        "STATUS_CSS_CLASSES",
        {Ticket.OPEN_STATUS: "danger", 6: "dark"},
    )
    def test_status_badge_class_custom_status_configurable(self):
        # A custom status (e.g. HELPDESK_TICKET_FORKED_STATUS = 6) gets its
        # color purely through the setting — no template edits required.
        self.ticket.status = 6
        self.assertEqual(self.ticket.get_status_badge_class, "dark")
        self.ticket.status = Ticket.OPEN_STATUS
        self.assertEqual(self.ticket.get_status_badge_class, "danger")

    def test_legacy_priority_css_class_unchanged(self):
        # row_class still feeds from the original (legacy) property, which
        # returns "" for the default priority 3 and "success" for priority 5,
        # preserving the upstream API contract.
        self.ticket.priority = 3
        self.assertEqual(self.ticket.get_priority_css_class, "")
        self.ticket.priority = 5
        self.assertEqual(self.ticket.get_priority_css_class, "success")


class DatatablesTicketListBadgeClassTests(TestCase):
    """The datatables endpoint exposes the computed badge classes per row,
    without altering the legacy row_class field."""

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )
        self.queue = Queue.objects.create(title="Payments", slug="payments")
        self.ticket = Ticket.objects.create(
            title="My card got double charged!",
            submitter_email="customer@example.com",
            queue=self.queue,
        )
        self.params = {
            "filtering": {"status__in": [1, 2]},
            "sorting": "created",
            "search_string": "",
            "sortreverse": False,
        }

    def test_endpoint_exposes_badge_classes(self):
        self.client.force_login(self.staff_user)
        query = query_to_base64(self.params)
        url = reverse("helpdesk:datatables_ticket_list", args=[query])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"][0]
        self.assertEqual(data["status_badge_class"], "danger")
        # Default ticket priority is 3, badge maps to "success" (as in the UI)
        self.assertEqual(data["priority_badge_class"], "success")
        # Legacy row_class is unchanged from upstream behavior ("" for priority 3)
        self.assertEqual(data["row_class"], "")
