from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import FollowUp, Queue, Ticket

User = get_user_model()


class FollowUpDirectionTests(TestCase):
    """The ``direction`` property behind the follow-up color coding."""

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )
        self.submitter = User.objects.create_user(
            username="submitter", password="testpass123"
        )
        self.queue = Queue.objects.create(title="Products", slug="products")
        self.ticket = Ticket.objects.create(
            title="Product not received",
            submitter_email="test@example.com",
            queue=self.queue,
        )

    def _followup(self, **kwargs):
        kwargs.setdefault("title", "Followup")
        return FollowUp.objects.create(ticket=self.ticket, **kwargs)

    def test_private_followup_is_internal(self):
        followup = self._followup(public=False, user=self.staff_user)

        self.assertEqual(followup.direction, FollowUp.DIRECTION_INTERNAL)

    def test_private_followup_stays_internal_even_when_received_by_email(self):
        # Visibility wins over authorship: a private note never went out.
        followup = self._followup(public=False, message_id="<abc@example.com>")

        self.assertEqual(followup.direction, FollowUp.DIRECTION_INTERNAL)

    def test_public_followup_by_staff_is_outbound(self):
        followup = self._followup(public=True, user=self.staff_user)

        self.assertEqual(followup.direction, FollowUp.DIRECTION_OUTBOUND)

    def test_public_followup_from_email_is_inbound(self):
        followup = self._followup(public=True, message_id="<abc@example.com>")

        self.assertEqual(followup.direction, FollowUp.DIRECTION_INBOUND)

    def test_public_followup_by_non_staff_user_is_inbound(self):
        followup = self._followup(public=True, user=self.submitter)

        self.assertEqual(followup.direction, FollowUp.DIRECTION_INBOUND)

    def test_public_followup_generated_by_helpdesk_is_outbound(self):
        # No author and no message ID means the helpdesk itself raised it, e.g.
        # an escalation. It is visible to the submitter, so it reads as outbound.
        followup = self._followup(public=True)

        self.assertEqual(followup.direction, FollowUp.DIRECTION_OUTBOUND)


class FollowUpDirectionRenderingTests(TestCase):
    """The staff ticket view marks up each follow-up with its direction."""

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )
        self.queue = Queue.objects.create(title="Products", slug="products")
        self.ticket = Ticket.objects.create(
            title="Product not received",
            submitter_email="test@example.com",
            queue=self.queue,
        )
        self.url = reverse("helpdesk:view", kwargs={"ticket_id": self.ticket.id})
        self.client.force_login(self.staff_user)

    def test_internal_followup_is_labeled_private(self):
        FollowUp.objects.create(
            ticket=self.ticket, title="Note", public=False, user=self.staff_user
        )

        r = self.client.get(self.url)

        self.assertContains(r, "followup-item-internal")
        self.assertContains(r, "Private")

    def test_outbound_followup_is_labeled_to_submitter(self):
        FollowUp.objects.create(
            ticket=self.ticket, title="Reply", public=True, user=self.staff_user
        )

        r = self.client.get(self.url)

        self.assertContains(r, "followup-item-outbound")
        self.assertContains(r, "To submitter")

    def test_inbound_followup_is_labeled_from_submitter(self):
        FollowUp.objects.create(
            ticket=self.ticket,
            title="E-Mail Received",
            public=True,
            message_id="<abc@example.com>",
        )

        r = self.client.get(self.url)

        self.assertContains(r, "followup-item-inbound")
        self.assertContains(r, "From submitter")
