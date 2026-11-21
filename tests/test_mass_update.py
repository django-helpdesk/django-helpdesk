from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import Queue, Ticket


class MassUpdateTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="mass-update-staff",
            is_staff=True,
        )
        self.queue = Queue.objects.create(
            title="Mass Update Queue",
            slug="mass-update",
        )
        self.ticket = Ticket.objects.create(
            queue=self.queue,
            title="Mass update test",
            description="Test bulk assignment",
        )
        self.client.force_login(self.staff)
        self.url = reverse("helpdesk:mass_update")

    def test_assign_and_unassign_create_followups(self):
        response = self.client.post(
            self.url,
            {"ticket_id": [self.ticket.pk], "action": f"assign_{self.staff.pk}"},
        )

        self.assertRedirects(response, reverse("helpdesk:list"))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_to, self.staff)
        self.assertTrue(
            self.ticket.followup_set.filter(
                title__contains="Assigned to",
                user=self.staff,
                public=True,
            ).exists()
        )

        response = self.client.post(
            self.url,
            {"ticket_id": [self.ticket.pk], "action": "unassign"},
        )

        self.assertRedirects(response, reverse("helpdesk:list"))
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.assigned_to)
        self.assertTrue(
            self.ticket.followup_set.filter(
                title="Unassigned in bulk update",
                user=self.staff,
                public=True,
            ).exists()
        )

    def test_close_and_delete_tickets(self):
        response = self.client.post(
            self.url,
            {"ticket_id": [self.ticket.pk], "action": "close"},
        )
        self.assertRedirects(response, reverse("helpdesk:list"))

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.CLOSED_STATUS)
        self.assertTrue(
            self.ticket.followup_set.filter(
                title="Closed in bulk update",
                public=False,
                new_status=Ticket.CLOSED_STATUS,
            ).exists()
        )

        ticket_id = self.ticket.pk
        response = self.client.post(
            self.url,
            {"ticket_id": [ticket_id], "action": "delete"},
        )
        self.assertRedirects(response, reverse("helpdesk:list"))
        self.assertFalse(Ticket.objects.filter(pk=ticket_id).exists())

    def test_set_and_remove_kbitem(self):
        from helpdesk.models import KBCategory, KBItem

        category = KBCategory.objects.create(
            name="Support",
            title="Support Articles",
            slug="mass-update-support",
            description="Support knowledge base",
        )
        item = KBItem.objects.create(
            category=category,
            title="Common question",
            question="How does this work?",
            answer="Follow these instructions.",
        )

        for action, expected in (
            (f"kbitem_{item.pk}", item.pk),
            ("kbitem_none", None),
        ):
            with self.subTest(action=action):
                response = self.client.post(
                    self.url,
                    {"ticket_id": [self.ticket.pk], "action": action},
                )
                self.assertRedirects(response, reverse("helpdesk:list"))
                self.ticket.refresh_from_db()
                self.assertEqual(self.ticket.kbitem_id, expected)

        self.assertEqual(
            self.ticket.followup_set.filter(
                title="KBItem set in bulk update",
                public=False,
            ).count(),
            2,
        )

    def test_close_public_creates_public_followup(self):
        from unittest.mock import patch

        with patch.object(
            Ticket,
            "send",
            side_effect=lambda *args, **kwargs: (
                kwargs["sent_to"].add("submitter@example.com")
                or ["submitter@example.com"]
            ),
        ):
            response = self.client.post(
                self.url,
                {"ticket_id": [self.ticket.pk], "action": "close_public"},
            )

        self.assertRedirects(response, reverse("helpdesk:list"))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.CLOSED_STATUS)

        followup = self.ticket.followup_set.get(
            title="Closed in bulk update",
            public=True,
        )
        self.assertEqual(followup.new_status, Ticket.CLOSED_STATUS)
        self.assertEqual(followup.email_recipients, ["submitter@example.com"])

    def test_close_public_notifies_assigned_owner_when_enabled(self):
        from unittest.mock import patch

        self.staff.email = "owner@example.com"
        self.staff.save(update_fields=["email"])
        self.staff.usersettings_helpdesk.email_on_ticket_change = True
        self.staff.usersettings_helpdesk.save()

        self.ticket.assigned_to = self.staff
        self.ticket.save(update_fields=["assigned_to"])

        with patch.object(Ticket, "send", return_value=[]) as mock_send:
            response = self.client.post(
                self.url,
                {"ticket_id": [self.ticket.pk], "action": "close_public"},
            )

        self.assertRedirects(response, reverse("helpdesk:list"))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.CLOSED_STATUS)

        roles = mock_send.call_args.args[0]
        self.assertIn("assigned_to", roles)
        self.assertEqual(roles["assigned_to"][0], "closed_owner")
