from http import HTTPStatus

from django.test import TestCase
from django.urls import resolve, reverse

from helpdesk.models import Queue, Ticket

from .helpers import get_staff_user


class ReportIndexViewTests(TestCase):
    """
    Test suite for the main Reports view which shows basic kpi stats and
    options to generate any report.
    """

    @classmethod
    def setUpTestData(cls):
        cls.template = "helpdesk/report_index.html"
        cls.url = reverse("helpdesk:report_index")
        cls.user = get_staff_user()
        # Create one queue and one ticket
        cls.queue = Queue.objects.create(title="Accounts", slug="accounts")
        cls.open_ticket = Ticket.objects.create(
            title="Account locked",
            status=Ticket.OPEN_STATUS,
            queue=cls.queue,
        )

    def test_url_resolves_correct_view(self):
        match = resolve(self.url)
        self.assertEqual(match.url_name, "report_index")

    def test_anonymous_user_cannot_access(self):
        # Act
        r = self.client.get(self.url)

        # Assert
        self.assertEqual(r.status_code, HTTPStatus.FOUND)
        self.assertRedirects(r, reverse("helpdesk:login") + "?next=/reports/")

    def test_report_index_url_works(self):
        # Act: Alice our support staff logs in
        self.client.force_login(self.user)

        r = self.client.get(self.url)

        # Assert
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, self.template)
        self.assertContains(r, "Reports")
        self.assertNotContains(r, "Hi I shouldn't be on this page")
