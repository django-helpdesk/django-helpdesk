"""The dependency pickers only reach tickets the user may open.

"Add dependency" and "Add resolves" link the ticket in the URL to a second
ticket chosen in the form. With per-queue permissions, that second ticket must
come from a queue the user can access, both in what the picker lists and in
what a submitted form is allowed to save.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from helpdesk import settings as helpdesk_settings
from helpdesk.models import Queue, Ticket, TicketDependency


@mock.patch.object(
    helpdesk_settings, "HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION", True
)
class DependencyPickerTests(TestCase):
    def setUp(self):
        granted = Queue.objects.create(title="Support", slug="support")
        foreign = Queue.objects.create(title="HR", slug="hr")
        self.staff = get_user_model().objects.create(username="agent", is_staff=True)
        self.staff.user_permissions.add(
            Permission.objects.get(codename=granted.permission_name[9:])
        )
        self.mine = Ticket.objects.create(title="Printer jam", queue=granted)
        self.other_mine = Ticket.objects.create(title="Screen flicker", queue=granted)
        self.foreign = Ticket.objects.create(
            title="CONFIDENTIAL salary review", queue=foreign
        )
        self.client.force_login(self.staff)

    def test_dependency_picker_lists_no_foreign_ticket(self):
        response = self.client.get(
            reverse("helpdesk:ticket_dependency_add", args=[self.mine.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Screen flicker")
        self.assertNotContains(response, "CONFIDENTIAL salary review")

    def test_resolves_picker_lists_no_foreign_ticket(self):
        response = self.client.get(
            reverse("helpdesk:ticket_resolves_add", args=[self.mine.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Screen flicker")
        self.assertNotContains(response, "CONFIDENTIAL salary review")

    def test_foreign_dependency_is_not_saved(self):
        self.client.post(
            reverse("helpdesk:ticket_dependency_add", args=[self.mine.id]),
            {"depends_on": self.foreign.id},
        )
        self.assertFalse(TicketDependency.objects.exists())

    def test_foreign_resolves_is_not_saved(self):
        self.client.post(
            reverse("helpdesk:ticket_resolves_add", args=[self.mine.id]),
            {"ticket": self.foreign.id},
        )
        self.assertFalse(TicketDependency.objects.exists())

    def test_dependency_between_accessible_tickets_is_saved(self):
        self.client.post(
            reverse("helpdesk:ticket_dependency_add", args=[self.mine.id]),
            {"depends_on": self.other_mine.id},
        )
        self.assertTrue(
            TicketDependency.objects.filter(
                ticket=self.mine, depends_on=self.other_mine
            ).exists()
        )

    def test_resolves_between_accessible_tickets_is_saved(self):
        self.client.post(
            reverse("helpdesk:ticket_resolves_add", args=[self.mine.id]),
            {"ticket": self.other_mine.id},
        )
        self.assertTrue(
            TicketDependency.objects.filter(
                ticket=self.other_mine, depends_on=self.mine
            ).exists()
        )
