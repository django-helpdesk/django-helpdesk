from django.test import TestCase
from django.urls import reverse

from helpdesk.models import Queue, Ticket

from .helpers import get_staff_user


class MergeTicketValidationTests(TestCase):
    def setUp(self):
        self.user = get_staff_user()
        self.client.force_login(self.user)
        self.queue = Queue.objects.create(
            title="Merge Validation",
            slug="merge-validation",
        )
        self.first = Ticket.objects.create(
            title="First merge ticket",
            queue=self.queue,
        )
        self.second = Ticket.objects.create(
            title="Second merge ticket",
            queue=self.queue,
        )
        self.url = reverse("helpdesk:merge_tickets")

    def test_chosen_ticket_must_be_among_selected_tickets(self):
        response = self.client.post(
            self.url + f"?tickets={self.first.pk}&tickets={self.second.pk}",
            {"chosen_ticket": "999999"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["ticket_select_form"],
            "tickets",
            "Please choose a ticket in which the others will be merged into.",
        )
        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertIsNone(self.first.merged_to)
        self.assertIsNone(self.second.merged_to)

    def test_merge_skips_custom_field_missing_on_source_ticket(self):
        from helpdesk.models import CustomField

        custom_field = CustomField.objects.create(
            name="missing_source_value",
            label="Missing source value",
            data_type="varchar",
        )
        self.first.ticketcustomfieldvalue_set.create(
            field=custom_field,
            value="Keep existing value",
        )

        self.second.submitter_email = "source@example.com"
        self.second.save(update_fields=["submitter_email"])

        response = self.client.post(
            self.url + f"?tickets={self.first.pk}&tickets={self.second.pk}",
            {
                "chosen_ticket": str(self.first.pk),
                custom_field.name: str(self.second.pk),
            },
        )

        self.assertRedirects(
            response,
            self.first.get_absolute_url(),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            self.first.ticketcustomfieldvalue_set.get(field=custom_field).value,
            "Keep existing value",
        )
        self.second.refresh_from_db()
        self.assertEqual(self.second.merged_to, self.first)
