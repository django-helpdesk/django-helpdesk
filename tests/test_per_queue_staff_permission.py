from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse
from django.utils import timezone

from helpdesk import settings
from helpdesk.models import (
    FollowUp,
    FollowUpAttachment,
    Queue,
    Ticket,
    TicketCC,
    TicketDependency,
)
from helpdesk.query import __Query__
from helpdesk.user import HelpdeskUser


class PerQueueStaffMembershipTestCase(TestCase):
    IDENTIFIERS = (1, 2)

    def setUp(self):
        """
        Create user_1 with access to queue_1 containing 2 ticket
        and    user_2 with access to queue_2 containing 4 tickets
        and superuser who should be able to access both queues
        """
        self.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = (
            settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
        )
        settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = True
        self.client = Client()
        User = get_user_model()

        self.superuser = User.objects.create(
            username="superuser",
            is_staff=True,
            is_superuser=True,
        )
        self.superuser.set_password("superuser")
        self.superuser.save()

        self.identifier_users = {}

        for identifier in self.IDENTIFIERS:
            queue = self.__dict__[f"queue_{identifier}"] = Queue.objects.create(
                title=f"Queue {identifier}",
                slug=f"q{identifier}",
            )

            user = self.__dict__[f"user_{identifier}"] = User.objects.create(
                username=f"User_{identifier}",
                is_staff=True,
                email=f"foo{identifier}@example.com",
            )
            user.set_password(str(identifier))
            user.save()
            self.identifier_users[identifier] = user

            # The prefix 'helpdesk.' must be trimmed
            p = Permission.objects.get(codename=queue.permission_name[9:])
            user.user_permissions.add(p)

            for ticket_number in range(1, identifier + 1):
                Ticket.objects.create(
                    title=f"Unassigned Ticket {ticket_number} in Queue {identifier}",
                    queue=queue,
                )
                Ticket.objects.create(
                    title=f"Ticket {ticket_number} in Queue {identifier} Assigned to User_{identifier}",
                    queue=queue,
                    assigned_to=user,
                )

    def tearDown(self):
        """
        Reset HELPDESK_ENABLE_PER_QUEUE_STAFF_MEMBERSHIP to original value
        """
        settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = (
            self.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
        )

    def test_dashboard_ticket_counts(self):
        """
        Check that the regular users' dashboard only shows 1 of the 2 queues,
        that user_1 only sees a total of 2 tickets, that user_2 sees a total of 4
        tickets, but that the superuser's dashboard shows all queues and tickets.
        """

        # Regular users
        for identifier in self.IDENTIFIERS:
            self.client.login(username=f"User_{identifier}", password=str(identifier))
            response = self.client.get(reverse("helpdesk:dashboard"))
            self.assertEqual(
                len(response.context["unassigned_tickets"]),
                identifier,
                "Unassigned tickets were not properly limited by queue membership",
            )
            self.assertEqual(
                response.context["basic_ticket_stats"]["open_ticket_stats"][0][1],
                identifier * 2,
                "Basic ticket stats were not properly limited by queue membership",
            )

        # Superuser
        self.client.login(username="superuser", password="superuser")
        response = self.client.get(reverse("helpdesk:dashboard"))
        self.assertEqual(
            len(response.context["unassigned_tickets"]),
            3,
            "Unassigned tickets were limited by queue membership for a superuser",
        )
        self.assertEqual(
            response.context["basic_ticket_stats"]["open_ticket_stats"][0][1]
            + response.context["basic_ticket_stats"]["open_ticket_stats"][1][1],
            6,
            "Basic ticket stats were limited by queue membership for a superuser",
        )

    def test_report_ticket_counts(self):
        """
        Check that the regular users' report only shows 1 of the 2 queues,
        that user_1 only sees a total of 2 tickets, that user_2 sees a total of 4
        tickets, but that the superuser's report shows all queues and tickets.
        """

        # Regular users
        for identifier in self.IDENTIFIERS:
            self.client.login(username=f"User_{identifier}", password=str(identifier))
            response = self.client.get(reverse("helpdesk:report_index"))
            self.assertEqual(
                len(response.context["dash_tickets"]),
                1,
                "The queues in dash_tickets were not properly limited by queue membership",
            )
            self.assertEqual(
                response.context["dash_tickets"][0]["open"],
                identifier * 2,
                "The tickets in dash_tickets were not properly limited by queue membership",
            )
            self.assertEqual(
                response.context["basic_ticket_stats"]["open_ticket_stats"][0][1],
                identifier * 2,
                "Basic ticket stats were not properly limited by queue membership",
            )

        # Superuser
        self.client.login(username="superuser", password="superuser")
        response = self.client.get(reverse("helpdesk:report_index"))
        self.assertEqual(
            len(response.context["dash_tickets"]),
            2,
            "The queues in dash_tickets were limited by queue membership for a superuser",
        )
        self.assertEqual(
            response.context["dash_tickets"][0]["open"]
            + response.context["dash_tickets"][1]["open"],
            6,
            "The tickets in dash_tickets were limited by queue membership for a superuser",
        )
        self.assertEqual(
            response.context["basic_ticket_stats"]["open_ticket_stats"][0][1]
            + response.context["basic_ticket_stats"]["open_ticket_stats"][1][1],
            6,
            "Basic ticket stats were limited by queue membership for a superuser",
        )

    def test_ticket_list_per_queue_user_restrictions(self):
        """
        Ensure that while the superuser can list all tickets, user_1 can only
        list the 2 tickets in his queue and user_2 can list only the 4 tickets
        in his queue.
        """
        # Regular users
        for identifier in self.IDENTIFIERS:
            self.client.login(username=f"User_{identifier}", password=str(identifier))
            response = self.client.get(reverse("helpdesk:list"))
            tickets = __Query__(
                HelpdeskUser(self.identifier_users[identifier]),
                base64query=response.context["urlsafe_query"],
            ).get()
            self.assertEqual(
                len(tickets),
                identifier * 2,
                "Ticket list was not properly limited by queue membership",
            )
            self.assertEqual(
                len(response.context["queue_choices"]),
                1,
                "Queue choices were not properly limited by queue membership",
            )
            self.assertEqual(
                response.context["queue_choices"][0],
                Queue.objects.get(title=f"Queue {identifier}"),
                "Queue choices were not properly limited by queue membership",
            )

        # Superuser
        self.client.login(username="superuser", password="superuser")
        response = self.client.get(reverse("helpdesk:list"))
        tickets = __Query__(
            HelpdeskUser(self.superuser), base64query=response.context["urlsafe_query"]
        ).get()
        self.assertEqual(
            len(tickets),
            6,
            "Ticket list was limited by queue membership for a superuser",
        )

    def test_ticket_reports_per_queue_user_restrictions(self):
        """
        Ensure that while the superuser can generate reports on all queues and
        tickets, user_1 can only generate reports for queue 1 and user_2 can
        only do so for queue 2
        """
        # Regular users
        for identifier in self.IDENTIFIERS:
            self.client.login(username=f"User_{identifier}", password=str(identifier))
            response = self.client.get(
                reverse("helpdesk:run_report", kwargs={"report": "userqueue"})
            )
            # Only two columns of data should be present: ticket counts for
            # unassigned and this user only
            self.assertEqual(
                len(response.context["data"]),
                2,
                "Queues in report were not properly limited by queue membership",
            )
            # Each user should see a total number of tickets equal to twice
            # their ID
            self.assertEqual(
                sum(
                    [sum(user_tickets[1:]) for user_tickets in response.context["data"]]
                ),
                identifier * 2,
                "Tickets in report were not properly limited by queue membership",
            )
            # Each user should only be able to pick 1 queue
            self.assertEqual(
                len(response.context["headings"]),
                2,
                "Queue choices were not properly limited by queue membership",
            )
            # The queue each user can pick should be the queue named after
            # their ID
            self.assertEqual(
                response.context["headings"][1],
                f"Queue {identifier}",
                "Queue choices were not properly limited by queue membership",
            )

        # Superuser
        self.client.login(username="superuser", password="superuser")
        response = self.client.get(
            reverse("helpdesk:run_report", kwargs={"report": "userqueue"})
        )
        # Superuser should see ticket counts for all two queues, which includes
        # three columns: unassigned and both user 1 and user 2
        self.assertEqual(
            len(response.context["data"][0]),
            3,
            "Queues in report were improperly limited by queue membership for a superuser",
        )
        # Superuser should see the total ticket count of three tickets
        self.assertEqual(
            sum([sum(user_tickets[1:]) for user_tickets in response.context["data"]]),
            6,
            "Tickets in report were improperly limited by queue membership for a superuser",
        )
        self.assertEqual(
            len(response.context["headings"]),
            3,
            "Queue choices were improperly limited by queue membership for a superuser",
        )


class PerQueuePermissionSecurityTestCase(TestCase):
    """
    Tests that per-queue staff permission checks are enforced on destructive
    endpoints. user_1 has access to queue_1 only and must be denied access to
    resources belonging to queue_2.
    """

    def setUp(self):
        self.original_setting = settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
        settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = True
        self.client = Client()
        User = get_user_model()

        self.queue_1 = Queue.objects.create(title="Queue 1", slug="q1")
        self.queue_2 = Queue.objects.create(title="Queue 2", slug="q2")

        self.user_1 = User.objects.create(
            username="user_1", is_staff=True, email="u1@example.com"
        )
        self.user_1.set_password("pass")
        self.user_1.save()
        p1 = Permission.objects.get(codename=self.queue_1.permission_name[9:])
        self.user_1.user_permissions.add(p1)

        self.ticket_1 = Ticket.objects.create(title="Ticket in Q1", queue=self.queue_1)
        self.ticket_2 = Ticket.objects.create(title="Ticket in Q2", queue=self.queue_2)
        self.ticket_2b = Ticket.objects.create(
            title="Ticket 2b in Q2", queue=self.queue_2
        )

        followup_2 = FollowUp.objects.create(
            ticket=self.ticket_2, title="FU", date=timezone.now()
        )
        self.attachment_2 = FollowUpAttachment.objects.create(
            followup=followup_2,
            file=SimpleUploadedFile(
                "secret.txt", b"content", content_type="text/plain"
            ),
        )

        self.cc_2 = TicketCC.objects.create(
            ticket=self.ticket_2, email="cc@example.com"
        )

        self.dep_2 = TicketDependency.objects.create(
            ticket=self.ticket_2, depends_on=self.ticket_1
        )

    def tearDown(self):
        settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = self.original_setting

    def _login_user_1(self):
        self.client.login(username="user_1", password="pass")

    def test_attachment_del_idor_blocked(self):
        """user_1 cannot delete an attachment from queue_2 by pairing their
        accessible ticket_1 id with queue_2's attachment id."""
        self._login_user_1()
        url = reverse(
            "helpdesk:attachment_del",
            kwargs={
                "ticket_id": self.ticket_1.id,
                "attachment_id": self.attachment_2.id,
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            FollowUpAttachment.objects.filter(id=self.attachment_2.id).exists()
        )

    def test_ticket_cc_del_blocked(self):
        """user_1 cannot delete a CC entry on a ticket in queue_2."""
        self._login_user_1()
        url = reverse(
            "helpdesk:ticket_cc_del",
            kwargs={"ticket_id": self.ticket_2.id, "cc_id": self.cc_2.id},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(TicketCC.objects.filter(id=self.cc_2.id).exists())

    def test_ticket_dependency_del_blocked(self):
        """user_1 cannot delete a dependency on a ticket in queue_2."""
        self._login_user_1()
        url = reverse(
            "helpdesk:ticket_dependency_del",
            kwargs={"ticket_id": self.ticket_2.id, "dependency_id": self.dep_2.id},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(TicketDependency.objects.filter(id=self.dep_2.id).exists())

    def test_ticket_resolves_del_blocked(self):
        """user_1 cannot delete a resolves-link on a ticket in queue_2."""
        self._login_user_1()
        url = reverse(
            "helpdesk:ticket_resolves_del",
            kwargs={"ticket_id": self.ticket_2.id, "dependency_id": self.dep_2.id},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(TicketDependency.objects.filter(id=self.dep_2.id).exists())

    def test_merge_tickets_blocked_for_inaccessible_queue(self):
        """user_1 cannot merge tickets when one belongs to queue_2."""
        self._login_user_1()
        url = (
            reverse("helpdesk:merge_tickets")
            + f"?tickets={self.ticket_2.id}&tickets={self.ticket_2b.id}"
        )
        response = self.client.post(url, {"chosen_ticket": self.ticket_2.id})
        self.assertEqual(response.status_code, 403)

    def test_rss_queue_blocked_for_inaccessible_queue(self):
        """user_1 cannot read the RSS feed for queue_2."""
        self._login_user_1()
        url = reverse("helpdesk:rss_queue", kwargs={"queue_slug": self.queue_2.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_view_ticket_redirects_with_error_for_inaccessible_queue(self):
        """user_1 is redirected to the ticket list with an error message when
        viewing a ticket in queue_2 instead of hitting a bare 403 page."""
        self._login_user_1()
        url = reverse("helpdesk:view", kwargs={"ticket_id": self.ticket_2.id})
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("helpdesk:list"))
        stored_messages = list(response.context["messages"])
        self.assertEqual(len(stored_messages), 1)
        self.assertEqual(stored_messages[0].level, messages.ERROR)
        self.assertEqual(
            str(stored_messages[0]),
            f"You don't have permission to view ticket - {self.ticket_2}.",
        )

    def test_view_ticket_allowed_for_accessible_queue(self):
        """The redirect only applies when permission is denied: user_1 can
        still view a ticket in their own queue."""
        self._login_user_1()
        url = reverse("helpdesk:view", kwargs={"ticket_id": self.ticket_1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ticket"].id, self.ticket_1.id)
        self.assertEqual(len(list(response.context["messages"])), 0)
