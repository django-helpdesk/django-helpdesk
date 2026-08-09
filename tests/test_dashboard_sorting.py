"""
The dashboard tables are sorted from `?ut_sort` / `?utcr_sort` / `?atrbcu_sort`
/ `?una_sort`, which used to be passed to order_by() as-is. Django resolves
double-underscore keys as relation traversals, so a staff user could order a
table by a column of an unrelated table (a queue's plaintext mailbox password,
another user's password hash, ...) and infer its value from the row order.
"""

from django.test import TestCase
from django.urls import reverse

from helpdesk.models import Queue, Ticket

from .helpers import get_staff_user

INJECTED_SORTS = [
    "queue__email_box_pass",
    "-queue__email_box_pass",
    "assigned_to__password",
    "-assigned_to__password",
]

SORT_PARAMS = ["ut_sort", "utcr_sort", "atrbcu_sort", "una_sort"]


class DashboardSortingTestCase(TestCase):
    def setUp(self):
        self.queue = Queue.objects.create(
            title="Test queue",
            slug="test_queue",
            email_box_pass="a-secret-mailbox-password",
        )
        self.ticket = Ticket.objects.create(
            title="Unassigned ticket",
            queue=self.queue,
            description="lol",
        )
        self.user = get_staff_user()
        self.client.login(username=self.user.username, password="password")

    def get_dashboard(self, **params):
        return self.client.get(reverse("helpdesk:dashboard"), params)

    def test_injected_sort_field_is_ignored(self):
        """Any sort key outside the allowlist falls back to the default sort."""
        for param in SORT_PARAMS:
            for sorting in INJECTED_SORTS:
                with self.subTest(param=param, sorting=sorting):
                    response = self.get_dashboard(**{param: sorting})
                    self.assertEqual(response.status_code, 200)
                    for context_var in (
                        "user_tickets_sort",
                        "user_tickets_closed_sort",
                        "all_tickets_reported_sort",
                        "unassigned_tickets_sort",
                    ):
                        self.assertEqual(response.context[context_var], "-created")

    def test_injected_sort_field_never_reaches_the_orm(self):
        """The queryset behind the table must not order by the injected path."""
        response = self.get_dashboard(una_sort="queue__email_box_pass")
        queryset = response.context["unassigned_tickets"].paginator.object_list
        self.assertEqual(list(queryset.query.order_by), ["-created"])

    def test_allowed_sort_fields_are_kept(self):
        for param, context_var in zip(
            SORT_PARAMS,
            [
                "user_tickets_sort",
                "user_tickets_closed_sort",
                "all_tickets_reported_sort",
                "unassigned_tickets_sort",
            ],
        ):
            for sorting in ("id", "-id", "priority", "-priority", "queue", "status"):
                with self.subTest(param=param, sorting=sorting):
                    response = self.get_dashboard(**{param: sorting})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.context[context_var], sorting)

    def test_default_sort_when_no_parameter_given(self):
        response = self.get_dashboard()
        self.assertEqual(response.context["unassigned_tickets_sort"], "-created")
