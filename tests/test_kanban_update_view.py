import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import Queue, Ticket


class KanbanUpdateTicketTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="kanban_tester",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )
        self.queue = Queue.objects.create(
            title="Kanban Support",
            slug="kanban-support",
        )
        self.ticket = Ticket.objects.create(
            title="Kanban ticket",
            queue=self.queue,
        )
        self.url = reverse(
            "helpdesk:kanban_update",
            kwargs={"ticket_id": self.ticket.pk},
        )
        self.client.force_login(self.user)

    def test_get_request_is_rejected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()["error"], "POST required")

    def test_valid_status_update_persists(self):
        response = self.client.post(
            self.url,
            json.dumps({"status": Ticket.CLOSED_STATUS}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "new_status": Ticket.CLOSED_STATUS},
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.CLOSED_STATUS)

    def test_invalid_payloads_do_not_change_ticket(self):
        original_status = self.ticket.status

        for payload in (
            "{invalid json",
            "{}",
            '{"status": "not-a-number"}',
        ):
            with self.subTest(payload=payload):
                response = self.client.post(
                    self.url,
                    payload,
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.json()["error"],
                    "Invalid data",
                )
                self.ticket.refresh_from_db()
                self.assertEqual(self.ticket.status, original_status)

    def test_unknown_status_is_rejected(self):
        response = self.client.post(
            self.url,
            json.dumps({"status": 999999}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid status")
        self.ticket.refresh_from_db()
        self.assertNotEqual(self.ticket.status, 999999)
