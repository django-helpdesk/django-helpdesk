"""Who gets through the access guards on helpdesk views.

Staff views are guarded by helpdesk_staff_member_required, superuser-only
views by superuser_required, and public views by protect_view.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.http import HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse

from helpdesk import settings as helpdesk_settings
from helpdesk.models import Queue, Ticket
from helpdesk.user import HelpdeskUser


class StaffViewGuardTests(TestCase):
    def setUp(self):
        self.url = reverse("helpdesk:list")

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_non_staff_user_is_sent_to_login(self):
        user = get_user_model().objects.create(username="customer")
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_staff_user_gets_the_view(self):
        user = get_user_model().objects.create(username="agent", is_staff=True)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class SuperuserViewGuardTests(TestCase):
    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(reverse("helpdesk:email_ignore"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("helpdesk:login"))

    def test_staff_user_who_is_not_superuser_is_refused(self):
        user = get_user_model().objects.create(username="agent", is_staff=True)
        self.client.force_login(user)
        response = self.client.get(reverse("helpdesk:email_ignore"))
        self.assertEqual(response.status_code, 403)


class PublicViewGuardTests(TestCase):
    def setUp(self):
        self.url = reverse("helpdesk:home")

    @mock.patch.object(helpdesk_settings, "HELPDESK_ANON_ACCESS_RAISES_404", True)
    def test_anonymous_user_gets_404_when_configured(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_public_view_protector_redirect_is_returned(self):
        def protector(request):
            return HttpResponseRedirect("/elsewhere/")

        with mock.patch.object(
            helpdesk_settings, "HELPDESK_PUBLIC_VIEW_PROTECTOR", protector
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/elsewhere/")


class AnonymousTicketAccessTests(TestCase):
    def test_anonymous_user_can_access_no_ticket(self):
        queue = Queue.objects.create(title="Queue", slug="queue")
        Ticket.objects.create(title="Ticket", queue=queue, description="d")
        self.assertFalse(HelpdeskUser(AnonymousUser()).accessible_tickets().exists())


@mock.patch.object(
    helpdesk_settings, "HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION", True
)
class MassUpdateQueueGuardTests(TestCase):
    def test_restricted_staff_only_updates_tickets_in_granted_queues(self):
        granted = Queue.objects.create(title="Granted", slug="granted")
        other = Queue.objects.create(title="Other", slug="other")
        staff = get_user_model().objects.create(username="agent", is_staff=True)
        staff.user_permissions.add(
            Permission.objects.get(codename=granted.permission_name[9:])
        )
        mine = Ticket.objects.create(title="Mine", queue=granted, description="d")
        foreign = Ticket.objects.create(title="Foreign", queue=other, description="d")

        self.client.force_login(staff)
        self.client.post(
            reverse("helpdesk:mass_update"),
            {"ticket_id": [mine.id, foreign.id], "action": "take"},
        )

        mine.refresh_from_db()
        foreign.refresh_from_db()
        self.assertEqual(mine.assigned_to, staff)
        self.assertIsNone(foreign.assigned_to)
