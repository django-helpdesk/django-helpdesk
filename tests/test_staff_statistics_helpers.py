from datetime import timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from helpdesk.views.staff import (
    calc_average_nbr_days_until_ticket_resolved,
    days_since_created,
    get_color_for_nbr_days,
)


class StaffStatisticsHelperTests(SimpleTestCase):
    def test_average_resolution_days(self):
        now = timezone.now()
        tickets = [
            SimpleNamespace(created=now - timedelta(days=2), modified=now),
            SimpleNamespace(created=now - timedelta(days=6), modified=now),
        ]

        self.assertEqual(
            calc_average_nbr_days_until_ticket_resolved(tickets),
            4,
        )

    def test_average_resolution_days_with_no_tickets(self):
        self.assertEqual(
            calc_average_nbr_days_until_ticket_resolved([]),
            0,
        )

    def test_color_classification_boundaries(self):
        for days, expected in (
            (0, "green"),
            (4, "green"),
            (5, "orange"),
            (9, "orange"),
            (10, "red"),
            (15, "red"),
        ):
            with self.subTest(days=days):
                self.assertEqual(get_color_for_nbr_days(days), expected)

    def test_days_since_created(self):
        now = timezone.now()
        ticket = SimpleNamespace(created=now - timedelta(days=7))

        self.assertEqual(days_since_created(now, ticket), 7)
