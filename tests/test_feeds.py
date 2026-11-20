from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from helpdesk.models import Queue
from helpdesk.views.feeds import (
    OpenTicketsByQueue,
    OpenTicketsByUser,
    UnassignedTickets,
)
from tests.helpers import create_ticket, get_staff_user


class TicketFeedsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_staff_user()
        cls.queue = Queue.objects.create(title="Support", slug="support")
        cls.other_queue = Queue.objects.create(title="Other", slug="other")
        cls.assigned_open = create_ticket(queue=cls.queue, assigned_to=cls.user)
        cls.assigned_reopened = create_ticket(
            queue=cls.queue, assigned_to=cls.user, status=2
        )
        cls.assigned_closed = create_ticket(
            queue=cls.queue, assigned_to=cls.user, status=4
        )
        cls.other_ticket = create_ticket(queue=cls.other_queue, assigned_to=cls.user)
        cls.unassigned = create_ticket(queue=cls.queue)

    def test_user_queue_feed_filters_tickets_and_builds_metadata(self):
        feed = OpenTicketsByUser()
        request = RequestFactory().get("/")
        request.user = self.user

        with patch(
            "helpdesk.views.feeds.HelpdeskUser.can_access_queue",
            return_value=True,
        ):
            obj = feed.get_object(
                request, user_name=self.user.username, queue_slug=self.queue.slug
            )

        self.assertEqual(obj["queue"], self.queue)
        self.assertIn("Support", feed.title(obj))
        self.assertIn("Support", feed.description(obj))
        self.assertEqual(
            feed.link(obj),
            f"{reverse('helpdesk:list')}?assigned_to={self.user.pk}&queue={self.queue.pk}",
        )
        self.assertCountEqual(
            feed.items(obj).values_list("pk", flat=True),
            [self.assigned_open.pk, self.assigned_reopened.pk],
        )
        self.assertEqual(
            feed.item_pubdate(self.assigned_open), self.assigned_open.created
        )
        self.assertEqual(feed.item_author_name(self.assigned_open), self.user.username)

    def test_user_queue_feed_rejects_inaccessible_queue(self):
        request = RequestFactory().get("/")
        request.user = self.user

        with (
            patch(
                "helpdesk.views.feeds.HelpdeskUser.can_access_queue",
                return_value=False,
            ),
            self.assertRaises(PermissionDenied),
        ):
            OpenTicketsByUser().get_object(
                request, user_name=self.user.username, queue_slug=self.queue.slug
            )

    def test_queue_feed_filters_open_tickets_and_builds_metadata(self):
        feed = OpenTicketsByQueue()
        request = RequestFactory().get("/")
        request.user = self.user

        with patch(
            "helpdesk.views.feeds.HelpdeskUser.can_access_queue",
            return_value=True,
        ):
            queue = feed.get_object(request, queue_slug=self.queue.slug)

        self.assertEqual(queue, self.queue)
        self.assertIn("Support", feed.title(queue))
        self.assertIn("Support", feed.description(queue))
        self.assertEqual(
            feed.link(queue), f"{reverse('helpdesk:list')}?queue={self.queue.pk}"
        )
        self.assertCountEqual(
            feed.items(queue).values_list("pk", flat=True),
            [self.assigned_open.pk, self.assigned_reopened.pk, self.unassigned.pk],
        )
        self.assertEqual(feed.item_pubdate(self.unassigned), self.unassigned.created)
        self.assertEqual(feed.item_author_name(self.assigned_open), self.user.username)
        self.assertEqual(feed.item_author_name(self.unassigned), "Unassigned")

    def test_author_fallbacks(self):
        self.assertEqual(
            OpenTicketsByUser().item_author_name(self.unassigned), "Unassigned"
        )
        self.assertEqual(
            UnassignedTickets().item_author_name(self.assigned_open),
            self.user.username,
        )
