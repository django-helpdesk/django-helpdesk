from datetime import date, timedelta
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from helpdesk.models import Queue, Ticket
from helpdesk.views.staff import (
    get_due_date_from_form_or_ticket,
    get_ticket_from_request_with_authorisation,
    get_time_spent_from_form,
)


class StaffViewHelperTests(TestCase):
    def setUp(self):
        self.queue = Queue.objects.create(title="Support", slug="support")
        self.ticket = Ticket.objects.create(
            title="Test ticket",
            queue=self.queue,
            submitter_email="submitter@example.com",
        )

    def test_public_ticket_lookup_requires_matching_credentials(self):
        factory = RequestFactory()

        request = factory.post(
            "/",
            {"mail": "submitter@example.com", "key": self.ticket.secret_key},
        )
        request.user = AnonymousUser()

        self.assertEqual(
            get_ticket_from_request_with_authorisation(
                request, str(self.ticket.pk), public=False
            ),
            self.ticket,
        )

        for credentials in (
            {"mail": "wrong@example.com", "key": self.ticket.secret_key},
            {"mail": "submitter@example.com", "key": "wrong-key"},
        ):
            with self.subTest(credentials=credentials):
                request = factory.post("/", credentials)
                request.user = AnonymousUser()

                with self.assertRaises(PermissionDenied):
                    get_ticket_from_request_with_authorisation(
                        request, str(self.ticket.pk), public=False
                    )

    def test_due_date_falls_back_to_existing_ticket_date(self):
        expected = date(2026, 11, 21)
        self.ticket.due_date = expected

        form = SimpleNamespace(cleaned_data={})

        self.assertEqual(
            get_due_date_from_form_or_ticket(form, self.ticket),
            expected,
        )

    def test_due_date_uses_legacy_date_components(self):
        form = SimpleNamespace(
            cleaned_data={
                "due_date_year": "2026",
                "due_date_month": "12",
                "due_date_day": "15",
            }
        )

        result = get_due_date_from_form_or_ticket(form, self.ticket)

        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 12)
        self.assertEqual(result.day, 15)

    def test_time_spent_parses_hours_and_minutes(self):
        form = SimpleNamespace(data={"time_spent": "02:30"})

        self.assertEqual(
            get_time_spent_from_form(form),
            timedelta(hours=2, minutes=30),
        )
