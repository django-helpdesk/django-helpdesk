"""What staff can change on tickets and follow-ups they can open.

Opening a ticket lets a staff member edit it, but not move it into a queue
they could not create a ticket in, and not rewrite other people's follow-ups:
only the author of a follow-up, or a superuser, may edit it, through the UI
or the API. The kanban board only shows tickets the user can open.
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from helpdesk import settings as helpdesk_settings
from helpdesk.forms import EditTicketForm
from helpdesk.models import FollowUp, Queue, Ticket

per_queue = mock.patch.object(
    helpdesk_settings, "HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION", True
)


def grant(user, queue):
    user.user_permissions.add(
        Permission.objects.get(codename=queue.permission_name[9:])
    )


@per_queue
class EditTicketQueueTests(TestCase):
    def setUp(self):
        self.support = Queue.objects.create(title="Support", slug="support")
        self.sales = Queue.objects.create(title="Sales", slug="sales")
        self.hr = Queue.objects.create(title="HR", slug="hr")
        self.staff = get_user_model().objects.create(username="agent", is_staff=True)
        grant(self.staff, self.support)
        grant(self.staff, self.sales)
        self.ticket = Ticket.objects.create(
            title="Printer jam",
            queue=self.support,
            submitter_email="customer@example.com",
        )
        self.url = reverse("helpdesk:edit", args=[self.ticket.id])
        self.client.force_login(self.staff)

    def post_queue(self, queue):
        data = {
            "title": self.ticket.title,
            "queue": queue.id,
            "submitter_email": self.ticket.submitter_email,
            "description": "",
            "priority": self.ticket.priority,
            "secret_key": self.ticket.secret_key,
        }
        return self.client.post(self.url, data)

    def test_ticket_cannot_be_moved_into_a_foreign_queue(self):
        self.post_queue(self.hr)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.queue, self.support)

    def test_ticket_can_be_moved_into_another_granted_queue(self):
        self.post_queue(self.sales)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.queue, self.sales)

    def test_form_does_not_offer_a_foreign_queue(self):
        response = self.client.get(self.url)
        queues = response.context["form"].fields["queue"].queryset
        self.assertIn(self.sales, queues)
        self.assertNotIn(self.hr, queues)

    def test_secret_key_is_not_editable(self):
        self.assertNotIn("secret_key", EditTicketForm.base_fields)


@per_queue
class KanbanQueueTests(TestCase):
    def test_board_lists_no_ticket_the_user_cannot_open(self):
        support = Queue.objects.create(title="Support", slug="support")
        public = Queue.objects.create(
            title="Public", slug="public", allow_public_submission=True
        )
        staff = get_user_model().objects.create(username="agent", is_staff=True)
        grant(staff, support)
        soon = timezone.now() + timedelta(weeks=1)
        Ticket.objects.create(title="Printer jam", queue=support, due_date=soon)
        Ticket.objects.create(
            title="CONFIDENTIAL web form", queue=public, due_date=soon
        )

        self.client.force_login(staff)
        response = self.client.get(reverse("helpdesk:kanban"))

        self.assertContains(response, "Printer jam")
        self.assertNotContains(response, "CONFIDENTIAL web form")


class FollowUpAuthorshipMixin:
    def setUp(self):
        User = get_user_model()
        self.queue = Queue.objects.create(title="Support", slug="support")
        self.author = User.objects.create(username="author", is_staff=True)
        self.colleague = User.objects.create(username="colleague", is_staff=True)
        self.root = User.objects.create(
            username="root", is_staff=True, is_superuser=True
        )
        self.ticket = Ticket.objects.create(title="Printer jam", queue=self.queue)
        self.followup = FollowUp.objects.create(
            ticket=self.ticket,
            title="Internal note",
            comment="Customer is on a payment plan",
            public=False,
            user=self.author,
            message_id="<note@example.com>",
        )


class FollowUpEditViewTests(FollowUpAuthorshipMixin, TestCase):
    def post_edit(self, user):
        self.client.force_login(user)
        return self.client.post(
            reverse("helpdesk:followup_edit", args=[self.ticket.id, self.followup.id]),
            {
                "ticket": self.ticket.id,
                "title": "Rewritten",
                "comment": "Rewritten",
                "public": "on",
                "new_status": "",
                "time_spent": "",
            },
        )

    def test_another_staff_member_cannot_edit(self):
        response = self.post_edit(self.colleague)
        self.assertEqual(response.status_code, 403)
        self.followup.refresh_from_db()
        self.assertEqual(self.followup.comment, "Customer is on a payment plan")
        self.assertFalse(self.followup.public)

    def test_another_staff_member_cannot_open_the_form(self):
        self.client.force_login(self.colleague)
        response = self.client.get(
            reverse("helpdesk:followup_edit", args=[self.ticket.id, self.followup.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_author_can_edit(self):
        self.post_edit(self.author)
        self.followup.refresh_from_db()
        self.assertEqual(self.followup.comment, "Rewritten")

    def test_superuser_can_edit(self):
        self.post_edit(self.root)
        self.followup.refresh_from_db()
        self.assertEqual(self.followup.comment, "Rewritten")

    @mock.patch.object(helpdesk_settings, "HELPDESK_SHOW_EDIT_BUTTON_FOLLOW_UP", False)
    def test_nobody_can_edit_when_editing_is_disabled(self):
        response = self.post_edit(self.author)
        self.assertEqual(response.status_code, 403)


class FollowUpApiTests(FollowUpAuthorshipMixin, APITestCase):
    def patch(self, user, data):
        self.client.force_authenticate(user)
        return self.client.patch(
            f"/api/followups/{self.followup.id}/", data, format="json"
        )

    def test_another_staff_member_cannot_update(self):
        response = self.patch(self.colleague, {"public": True})
        self.assertEqual(response.status_code, 403)
        self.followup.refresh_from_db()
        self.assertFalse(self.followup.public)

    def test_another_staff_member_cannot_delete(self):
        self.client.force_authenticate(self.colleague)
        response = self.client.delete(f"/api/followups/{self.followup.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(FollowUp.objects.filter(id=self.followup.id).exists())

    def test_author_who_is_not_superuser_cannot_delete(self):
        self.client.force_authenticate(self.author)
        response = self.client.delete(f"/api/followups/{self.followup.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(FollowUp.objects.filter(id=self.followup.id).exists())

    def test_superuser_can_delete(self):
        self.client.force_authenticate(self.root)
        response = self.client.delete(f"/api/followups/{self.followup.id}/")
        self.assertEqual(response.status_code, 204)

    def test_author_update_cannot_change_attribution_ticket_or_message_id(self):
        other_ticket = Ticket.objects.create(title="Other", queue=self.queue)
        response = self.patch(
            self.author,
            {
                "comment": "Updated",
                "user": self.root.id,
                "ticket": other_ticket.id,
                "message_id": "<hijack@example.com>",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.followup.refresh_from_db()
        self.assertEqual(self.followup.comment, "Updated")
        self.assertEqual(self.followup.user, self.author)
        self.assertEqual(self.followup.ticket, self.ticket)
        self.assertEqual(self.followup.message_id, "<note@example.com>")

    def test_superuser_can_update(self):
        response = self.patch(self.root, {"comment": "Updated"})
        self.assertEqual(response.status_code, 200)
        self.followup.refresh_from_db()
        self.assertEqual(self.followup.comment, "Updated")
