from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import Queue, Ticket, TicketDependency


class TicketDependencyViewTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="dependency-view-staff",
            is_staff=True,
        )
        self.queue = Queue.objects.create(
            title="Dependency View Queue",
            slug="dependency-view",
        )
        self.ticket = Ticket.objects.create(
            queue=self.queue,
            title="Main ticket",
            description="Main ticket description",
        )
        self.other = Ticket.objects.create(
            queue=self.queue,
            title="Related ticket",
            description="Related ticket description",
        )
        self.client.force_login(self.staff)

    def test_add_and_delete_dependency(self):
        add_url = reverse("helpdesk:ticket_dependency_add", args=[self.ticket.pk])
        response = self.client.post(
            add_url,
            {"depends_on": self.other.pk},
        )
        self.assertRedirects(response, self.ticket.get_absolute_url())

        dependency = TicketDependency.objects.get(
            ticket=self.ticket,
            depends_on=self.other,
        )

        delete_url = reverse(
            "helpdesk:ticket_dependency_del",
            args=[self.ticket.pk, dependency.pk],
        )
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(TicketDependency.objects.filter(pk=dependency.pk).exists())

        response = self.client.post(delete_url)
        self.assertRedirects(
            response,
            reverse("helpdesk:view", args=[self.ticket.pk]),
        )
        self.assertFalse(TicketDependency.objects.filter(pk=dependency.pk).exists())

    def test_add_and_delete_resolves_relationship(self):
        add_url = reverse("helpdesk:ticket_resolves_add", args=[self.other.pk])
        response = self.client.post(
            add_url,
            {"ticket": self.ticket.pk},
        )
        self.assertRedirects(response, self.other.get_absolute_url())

        dependency = TicketDependency.objects.get(
            ticket=self.ticket,
            depends_on=self.other,
        )

        delete_url = reverse(
            "helpdesk:ticket_resolves_del",
            args=[self.ticket.pk, dependency.pk],
        )
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(TicketDependency.objects.filter(pk=dependency.pk).exists())

        response = self.client.post(delete_url)
        self.assertRedirects(
            response,
            reverse("helpdesk:view", args=[self.other.pk]),
        )
        self.assertFalse(TicketDependency.objects.filter(pk=dependency.pk).exists())
