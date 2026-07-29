from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import resolve, reverse

from helpdesk.forms import CreateChecklistForm, EditTicketCustomFieldForm, TicketForm
from helpdesk.models import FollowUp, FollowUpAttachment, Queue, Ticket

User = get_user_model()


class StaffTicketViewTests(TestCase):
    """
    Test suite for the internal staff view to see details of a ticket.
    """

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staffuser1", password="testpass123", is_staff=True
        )
        self.queue = Queue.objects.create(title="Products", slug="products")
        self.ticket = Ticket.objects.create(
            title="Product not received",
            submitter_email="test@example.com",
            queue=self.queue,
        )
        self.url = reverse("helpdesk:view", kwargs={"ticket_id": self.ticket.id})
        self.template = "helpdesk/ticket.html"

    def test_url_resolves_correct_view(self):
        match = resolve(self.url)
        self.assertEqual(match.url_name, "view")

    def test_anonymous_user_cannot_access(self):
        # Arrange
        login_url = "{}?next={}".format(reverse("helpdesk:login"), self.url)

        # Act
        # Make an anonymous user directly access the ticket detail url
        r = self.client.get(self.url)

        # Assert
        # User should be redirected to login screen
        self.assertEqual(r.status_code, HTTPStatus.FOUND)
        self.assertRedirects(r, login_url)
        self.assertTemplateNotUsed(self.template)

    def test_staff_user_can_access_ticket_details(self):
        # Arrange: staff user logs in
        self.client.force_login(self.staff_user)

        # Act
        r = self.client.get(self.url)

        # Assert
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, self.template)
        self.assertNotContains(r, "I should not be on this page")

        # Check basic details
        self.assertContains(r, self.ticket.title)
        self.assertEqual(r.context["ticket"], self.ticket)

        # Check forms in context
        self.assertIsInstance(r.context["form"], TicketForm)
        self.assertIsInstance(r.context["checklist_form"], CreateChecklistForm)
        self.assertIsInstance(r.context["customfields_form"], EditTicketCustomFieldForm)

    def test_staff_user_can_assign_ticket_to_herself(self):
        # Arrange: Make staff user log in
        # prepare take url with a GET param

        self.client.force_login(self.staff_user)
        take_url = f"{self.url}?take"

        # Make sure new ticket is not assigned to anyone
        self.assertIsNone(self.ticket.assigned_to)

        # Act: staff user want to take the ticket for herself
        r = self.client.get(take_url, follow=True)

        # Assert
        self.ticket.refresh_from_db()

        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertRedirects(r, self.url)
        self.assertEqual(self.ticket.assigned_to, self.staff_user)

    def _add_attachments(self, count):
        followup = FollowUp.objects.create(ticket=self.ticket, title="Followup")
        for i in range(count):
            FollowUpAttachment.objects.create(
                followup=followup,
                file=SimpleUploadedFile(f"file{i}.txt", b"content"),
            )

    def test_few_attachments_shown_without_collapse(self):
        self.client.force_login(self.staff_user)
        self._add_attachments(3)

        r = self.client.get(self.url)

        self.assertEqual(r.context["ticket_attachments"].count(), 3)
        self.assertNotContains(r, "older attachment")

    def test_many_attachments_are_collapsed(self):
        self.client.force_login(self.staff_user)
        self._add_attachments(8)

        r = self.client.get(self.url)

        self.assertEqual(r.context["ticket_attachments"].count(), 8)
        self.assertContains(r, "Show 5 older attachments")
        self.assertContains(r, 'id="olderAttachments"')
