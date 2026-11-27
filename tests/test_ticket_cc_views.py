from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import Queue, Ticket, TicketCC


class TicketCCViewTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="ticket-cc-staff",
            is_staff=True,
        )
        self.queue = Queue.objects.create(
            title="Ticket CC Queue",
            slug="ticket-cc-tests",
        )
        self.ticket = Ticket.objects.create(
            queue=self.queue,
            title="Ticket CC test",
            description="Test CC management",
        )
        self.client.force_login(self.staff)

    def test_add_email_and_reject_duplicate(self):
        url = reverse("helpdesk:ticket_cc_add", args=[self.ticket.pk])
        data = {"email": "watcher@example.com"}

        response = self.client.post(url, data)
        self.assertRedirects(
            response,
            reverse("helpdesk:ticket_cc", args=[self.ticket.pk]),
        )
        self.assertEqual(
            TicketCC.objects.filter(
                ticket=self.ticket,
                email="watcher@example.com",
            ).count(),
            1,
        )

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "email",
            "Impossible to add twice the same email address",
        )
        self.assertEqual(TicketCC.objects.filter(ticket=self.ticket).count(), 1)

    def test_add_user_and_reject_duplicate(self):
        user = get_user_model().objects.create_user(
            username="ticket-cc-follower",
            email="follower@example.com",
            is_staff=True,
        )
        url = reverse("helpdesk:ticket_cc_add", args=[self.ticket.pk])
        data = {"user": user.pk}

        response = self.client.post(url, data)
        self.assertRedirects(
            response,
            reverse("helpdesk:ticket_cc", args=[self.ticket.pk]),
        )
        self.assertTrue(TicketCC.objects.filter(ticket=self.ticket, user=user).exists())

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "user",
            "Impossible to add twice the same user",
        )
        self.assertEqual(TicketCC.objects.filter(ticket=self.ticket).count(), 1)

    def test_delete_cc(self):
        cc = TicketCC.objects.create(
            ticket=self.ticket,
            email="remove@example.com",
        )
        url = reverse(
            "helpdesk:ticket_cc_del",
            args=[self.ticket.pk, cc.pk],
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(TicketCC.objects.filter(pk=cc.pk).exists())

        response = self.client.post(url)
        self.assertRedirects(
            response,
            reverse("helpdesk:ticket_cc", args=[self.ticket.pk]),
        )
        self.assertFalse(TicketCC.objects.filter(pk=cc.pk).exists())

    def test_edit_email_cc(self):
        cc = TicketCC.objects.create(
            ticket=self.ticket,
            email="watcher@example.com",
            can_view=True,
            can_update=False,
        )
        url = reverse("helpdesk:ticket_cc_edit", args=[self.ticket.pk, cc.pk])
        list_url = reverse("helpdesk:ticket_cc", args=[self.ticket.pk])

        self.assertContains(self.client.get(list_url), url)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "helpdesk/ticket_cc_edit.html")
        form = response.context["form"]
        self.assertEqual(set(form.fields), {"can_view", "can_update"})
        self.assertTrue(form.initial["can_view"])
        self.assertFalse(form.initial["can_update"])

        response = self.client.post(
            url,
            {"can_update": "on", "email": "changed@example.com"},
        )
        self.assertRedirects(response, list_url)

        cc.refresh_from_db()
        self.assertFalse(cc.can_view)
        self.assertTrue(cc.can_update)
        self.assertEqual(cc.email, "watcher@example.com")
        self.assertEqual(cc.ticket_id, self.ticket.pk)
        self.assertIsNone(cc.user_id)
        self.assertEqual(TicketCC.objects.filter(ticket=self.ticket).count(), 1)

    def test_edit_user_cc(self):
        user = get_user_model().objects.create_user(
            username="edit-cc-follower",
            email="follower@example.com",
        )
        cc = TicketCC.objects.create(
            ticket=self.ticket,
            user=user,
            can_view=False,
            can_update=True,
        )
        url = reverse("helpdesk:ticket_cc_edit", args=[self.ticket.pk, cc.pk])

        response = self.client.post(
            url,
            {"can_view": "on", "user": self.staff.pk},
        )
        self.assertRedirects(
            response,
            reverse("helpdesk:ticket_cc", args=[self.ticket.pk]),
        )

        cc.refresh_from_db()
        self.assertTrue(cc.can_view)
        self.assertFalse(cc.can_update)
        self.assertEqual(cc.user_id, user.pk)
        self.assertEqual(cc.ticket_id, self.ticket.pk)

    def test_edit_cc_from_different_ticket_blocked(self):
        other = Ticket.objects.create(
            queue=self.queue,
            title="Other ticket",
        )
        cc = TicketCC.objects.create(
            ticket=other,
            email="other@example.com",
        )
        url = reverse("helpdesk:ticket_cc_edit", args=[self.ticket.pk, cc.pk])

        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"can_view": "on"}).status_code, 404)
        cc.refresh_from_db()
        self.assertFalse(cc.can_view)

    @patch("helpdesk.settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION", True)
    def test_edit_cc_without_queue_permission_blocked(self):
        cc = TicketCC.objects.create(
            ticket=self.ticket,
            email="restricted@example.com",
        )
        url = reverse("helpdesk:ticket_cc_edit", args=[self.ticket.pk, cc.pk])

        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"can_view": "on"}).status_code, 403)
        cc.refresh_from_db()
        self.assertFalse(cc.can_view)

    def test_edit_cc_non_staff_blocked(self):
        user = get_user_model().objects.create_user(
            username="non-staff-cc",
            email="customer@example.com",
        )
        self.client.force_login(user)
        cc = TicketCC.objects.create(
            ticket=self.ticket,
            email="watcher@example.com",
        )
        url = reverse("helpdesk:ticket_cc_edit", args=[self.ticket.pk, cc.pk])

        response = self.client.post(url, {"can_view": "on"})
        self.assertIn(response.status_code, (302, 403))
        cc.refresh_from_db()
        self.assertFalse(cc.can_view)
