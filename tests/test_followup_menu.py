from unittest import mock

from django.test import TestCase
from django.urls import reverse

from helpdesk import settings as helpdesk_settings
from helpdesk.models import FollowUp, Queue, Ticket

from .helpers import get_user

MENU_TOGGLE = "fa-ellipsis-vertical"


class FollowUpMenuTests(TestCase):
    """The per follow-up action menu on the staff ticket view."""

    def setUp(self):
        self.queue = Queue.objects.create(title="Products", slug="products")
        self.ticket = Ticket.objects.create(
            title="Product not received",
            submitter_email="test@example.com",
            queue=self.queue,
        )
        self.url = reverse("helpdesk:view", kwargs={"ticket_id": self.ticket.id})

    def _login(self, username, is_superuser=False):
        user = get_user(username=username, is_staff=True, is_superuser=is_superuser)
        self.client.login(username=user.get_username(), password="password")
        return user

    def _followup(self, user=None):
        return FollowUp.objects.create(
            ticket=self.ticket, title="Followup", public=True, user=user
        )

    def test_menu_is_offered_on_own_followup(self):
        user = self._login("owner")
        self._followup(user=user)

        response = self.client.get(self.url)

        self.assertContains(response, MENU_TOGGLE)
        self.assertContains(
            response,
            reverse("helpdesk:followup_edit", args=[self.ticket.id, self._pk()]),
        )

    def test_no_menu_on_a_colleagues_followup(self):
        author = get_user(username="author", is_staff=True)
        self._login("viewer")
        self._followup(user=author)

        response = self.client.get(self.url)

        # Not the author and not a superuser: nothing to offer, so no toggle.
        self.assertNotContains(response, MENU_TOGGLE)

    def test_no_menu_on_a_followup_without_an_author(self):
        # E-mailed replies and publicly submitted tickets have no author, and
        # editing those is not offered to anyone, superuser included.
        self._login("boss", is_superuser=True)
        self._followup()

        response = self.client.get(self.url)

        self.assertNotContains(response, MENU_TOGGLE)

    def test_superuser_is_offered_the_menu_on_a_colleagues_followup(self):
        author = get_user(username="author", is_staff=True)
        self._login("boss", is_superuser=True)
        self._followup(user=author)

        response = self.client.get(self.url)

        self.assertContains(response, MENU_TOGGLE)

    def test_superuser_can_delete_a_followup_without_an_author(self):
        self._login("boss", is_superuser=True)
        self._followup()

        with mock.patch.object(
            helpdesk_settings, "HELPDESK_SHOW_DELETE_BUTTON_SUPERUSER_FOLLOW_UP", True
        ):
            response = self.client.get(self.url)

        self.assertContains(response, MENU_TOGGLE)
        self.assertContains(
            response,
            reverse("helpdesk:followup_delete", args=[self.ticket.id, self._pk()]),
        )
        self.assertNotContains(
            response,
            reverse("helpdesk:followup_edit", args=[self.ticket.id, self._pk()]),
        )

    def test_no_menu_when_the_edit_button_is_turned_off(self):
        user = self._login("owner")
        self._followup(user=user)

        with mock.patch.object(
            helpdesk_settings, "HELPDESK_SHOW_EDIT_BUTTON_FOLLOW_UP", False
        ):
            response = self.client.get(self.url)

        self.assertNotContains(response, MENU_TOGGLE)

    def _pk(self):
        return self.ticket.followup_set.get().id
