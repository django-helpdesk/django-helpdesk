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
