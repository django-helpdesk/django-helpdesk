from datetime import UTC, datetime
from http import HTTPStatus

from django.test import TestCase
from django.urls import resolve, reverse

from helpdesk.models import Queue, Ticket

from .helpers import get_staff_user


class RunReportViewTests(TestCase):
    """
    Test suite for the run report view which can render different types of reports.
    """

    @classmethod
    def setUpTestData(cls):
        cls.template = "helpdesk/report_output.html"
        cls.user = get_staff_user()
        cls.url = reverse("helpdesk:run_report", args=["userpriority"])
        cls.queue = Queue.objects.create(title="Accounts", slug="accounts")
        cls.open_ticket = Ticket.objects.create(
            title="Account locked",
            status=Ticket.OPEN_STATUS,
            queue=cls.queue,
        )

    def test_url_resolves_correct_view(self):
        match = resolve(self.url)
        self.assertEqual(match.url_name, "run_report")

    def test_anonymous_user_cannot_access(self):
        # Act
        r = self.client.get(self.url)

        # Assert
        self.assertEqual(r.status_code, HTTPStatus.FOUND)
        self.assertRedirects(r, reverse("helpdesk:login") + f"?next={self.url}")

    def test_report_generation_works(self):
        # Act: Alice our support staff logs in
        self.client.force_login(self.user)

        r = self.client.get(self.url)

        # Assert
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, self.template)
        self.assertContains(r, "Reports")
        self.assertNotContains(r, "Hi I shouldn't be on this page")

    def _set_created(self, ticket, year, month):
        Ticket.objects.filter(pk=ticket.pk).update(
            created=datetime(year, month, 15, tzinfo=UTC)
        )

    def test_monthly_report_lists_each_month_once(self):
        """Periods run from the first ticket's month to the last one's, inclusive."""
        self._set_created(self.open_ticket, 2025, 11)
        later = Ticket.objects.create(title="Later", queue=self.queue)
        self._set_created(later, 2026, 1)
        self.client.force_login(self.user)

        r = self.client.get(reverse("helpdesk:run_report", args=["usermonth"]))

        self.assertEqual(r.context["headings"][1:], ["2025-11", "2025-12", "2026-1"])

    def test_monthly_report_with_a_single_month(self):
        self._set_created(self.open_ticket, 2026, 3)
        self.client.force_login(self.user)

        r = self.client.get(reverse("helpdesk:run_report", args=["queuemonth"]))

        self.assertEqual(r.context["headings"][1:], ["2026-3"])

    def test_remaining_report_types_render_correct_headings(self):
        self.client.force_login(self.user)

        cases = (
            ("userstatus", "User by Status", "bar"),
            ("queuepriority", "Queue by Priority", "bar"),
            ("queuestatus", "Queue by Status", "bar"),
            (
                "daysuntilticketclosedbymonth",
                "Days until ticket closed by Month",
                "line",
            ),
        )

        for report, expected_title, expected_charttype in cases:
            with self.subTest(report=report):
                response = self.client.get(
                    reverse("helpdesk:run_report", args=[report])
                )
                self.assertEqual(response.status_code, HTTPStatus.OK)
                self.assertTemplateUsed(response, self.template)
                self.assertEqual(response.context["title"], expected_title)
                self.assertEqual(response.context["charttype"], expected_charttype)

    def test_days_until_closed_report_calculates_average(self):
        from datetime import timedelta

        created = datetime(2026, 3, 10, tzinfo=UTC)
        tickets = [
            self.open_ticket,
            Ticket.objects.create(title="Second closed ticket", queue=self.queue),
        ]

        for ticket, days in zip(tickets, (2, 4), strict=True):
            Ticket.objects.filter(pk=ticket.pk).update(
                status=Ticket.CLOSED_STATUS,
                created=created,
                modified=created + timedelta(days=days),
            )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("helpdesk:run_report", args=["daysuntilticketclosedbymonth"])
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.context["headings"][1:], ["2026-3"])
        self.assertEqual(response.context["data"], [["Accounts", 3.0]])
        self.assertEqual(response.context["total_data"], ["Total", "3.0"])
