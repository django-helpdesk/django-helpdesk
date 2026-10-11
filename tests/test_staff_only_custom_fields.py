"""Staff-only custom fields stay out of everything the submitter can see.

The public ticket view and `/api/user_tickets/` both serve the submitter, so
neither may show the value of a custom field marked `staff_only`, nor the
history of its changes. Staff keep seeing everything.
"""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APITestCase

from helpdesk.models import (
    CustomField,
    FollowUp,
    Queue,
    Ticket,
    TicketCustomFieldValue,
)


class StaffOnlyCustomFieldsMixin:
    def setUp(self):
        self.queue = Queue.objects.create(title="Queue", slug="queue")
        self.ticket = Ticket.objects.create(
            title="Need help",
            queue=self.queue,
            description="d",
            submitter_email="submitter@example.com",
        )
        self.internal = CustomField.objects.create(
            name="internal_risk",
            label="Internal Risk Score",
            data_type="varchar",
            max_length=100,
            staff_only=True,
        )
        self.public = CustomField.objects.create(
            name="order_number",
            label="Order Number",
            data_type="varchar",
            max_length=100,
            staff_only=False,
        )
        TicketCustomFieldValue.objects.create(
            ticket=self.ticket, field=self.internal, value="FRAUD-RISK-9000"
        )
        TicketCustomFieldValue.objects.create(
            ticket=self.ticket, field=self.public, value="ORDER-1234"
        )
        followup = FollowUp.objects.create(
            ticket=self.ticket, title="Staff update", public=True
        )
        followup.ticketchange_set.create(
            field=self.internal.name,
            old_value="LOW-RISK-1",
            new_value="FRAUD-RISK-9000",
        )
        followup.ticketchange_set.create(
            field=self.public.name, old_value="ORDER-0000", new_value="ORDER-1234"
        )


class PublicTicketViewTestCase(StaffOnlyCustomFieldsMixin, TestCase):
    def get_public_view(self):
        response = self.client.get(
            reverse("helpdesk:public_view"),
            {
                "ticket": self.ticket.ticket_for_url,
                "email": self.ticket.submitter_email,
                "key": self.ticket.secret_key,
            },
        )
        self.assertTemplateUsed(response, "helpdesk/public_view_ticket.html")
        return response

    def test_staff_only_value_is_not_shown(self):
        response = self.get_public_view()
        self.assertNotContains(response, "Internal Risk Score")
        self.assertNotContains(response, "FRAUD-RISK-9000")

    def test_staff_only_change_history_is_not_shown(self):
        response = self.get_public_view()
        self.assertNotContains(response, "LOW-RISK-1")
        self.assertNotContains(response, self.internal.name)

    def test_public_field_value_and_history_are_still_shown(self):
        response = self.get_public_view()
        self.assertContains(response, "Order Number")
        self.assertContains(response, "ORDER-1234")
        self.assertContains(response, "ORDER-0000")

    def test_query_count_does_not_grow_with_follow_ups(self):
        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.get_public_view()
            return len(queries)

        before = count_queries()
        for i in range(5):
            followup = FollowUp.objects.create(
                ticket=self.ticket, title=f"Update {i}", public=True
            )
            followup.ticketchange_set.create(
                field=self.internal.name, old_value="a", new_value="b"
            )
        self.assertEqual(count_queries(), before)


class UserTicketsApiTestCase(StaffOnlyCustomFieldsMixin, APITestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.submitter = User.objects.create(
            username="submitter", email="submitter@example.com"
        )
        self.staff = User.objects.create(
            username="staff", email="staff@example.com", is_staff=True
        )

    def test_submitter_does_not_get_staff_only_field(self):
        self.client.force_authenticate(self.submitter)
        response = self.client.get("/api/user_tickets/")
        self.assertEqual(response.status_code, 200)
        ticket = response.json()["results"][0]
        self.assertNotIn("custom_internal_risk", ticket)
        self.assertNotIn("FRAUD-RISK-9000", response.content.decode())
        self.assertEqual(ticket["custom_order_number"], "ORDER-1234")

    def test_staff_still_get_staff_only_field(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(f"/api/tickets/{self.ticket.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["custom_internal_risk"], "FRAUD-RISK-9000")
