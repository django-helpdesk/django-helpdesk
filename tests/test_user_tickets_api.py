"""`/api/user_tickets/` must not treat a missing address as an identity.

The endpoint answers "the tickets submitted by the current user" by matching
`Ticket.submitter_email` against `User.email`. Neither field is verified and
both can be empty, so an account with no address used to match every ticket
with no address. The model default for `submitter_email` is NULL, which does
not collide, but anything created through a form stores "" instead, and that
is the ordinary path.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from helpdesk.models import Queue, Ticket


class UserTicketsIdentityTestCase(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.queue = Queue.objects.create(title="Queue", slug="queue")
        self.no_address = User.objects.create(username="no-address")
        self.owner = User.objects.create(username="owner", email="owner@example.com")

    def titles_for(self, user):
        self.client.force_authenticate(user)
        response = self.client.get("/api/user_tickets/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        return sorted(t["title"] for t in body.get("results", body))

    def test_an_account_without_an_address_gets_nothing(self):
        """Even when tickets carry an empty submitter address, which is what a
        form stores when the field is left blank."""
        Ticket.objects.create(
            title="submitted anonymously through the form",
            queue=self.queue,
            description="d",
            submitter_email="",
        )
        Ticket.objects.create(
            title="created without a submitter at all",
            queue=self.queue,
            description="d",
        )
        self.assertEqual(self.titles_for(self.no_address), [])

    def test_an_account_with_an_address_still_gets_its_own_tickets(self):
        """The control: the endpoint must keep working for everyone else."""
        Ticket.objects.create(
            title="mine",
            queue=self.queue,
            description="d",
            submitter_email="owner@example.com",
        )
        Ticket.objects.create(
            title="someone else's",
            queue=self.queue,
            description="d",
            submitter_email="other@example.com",
        )
        Ticket.objects.create(
            title="no submitter", queue=self.queue, description="d", submitter_email=""
        )
        self.assertEqual(self.titles_for(self.owner), ["mine"])

    def test_the_match_stays_case_sensitive(self):
        """Deliberately exact. An address differing only in case identifies a
        different mailbox as far as this endpoint can tell, since nothing
        verifies either side. Switching to __iexact would look like a usability
        fix and would widen the same bug: more accounts matching tickets they
        did not submit."""
        Ticket.objects.create(
            title="lower case submitter",
            queue=self.queue,
            description="d",
            submitter_email="owner@example.com",
        )
        User = get_user_model()
        mixed_case = User.objects.create(
            username="mixed-case", email="Owner@Example.com"
        )
        self.assertEqual(self.titles_for(mixed_case), [])


class SubmitterEmailStorageTestCase(TestCase):
    """Pins the premise of the test above: a blank field is stored as "" rather
    than NULL, so the collision is reachable through the ordinary flow rather
    than only through code that sets the column explicitly."""

    def test_the_submit_form_stores_an_empty_string(self):
        User = get_user_model()
        queue = Queue.objects.create(
            title="Queue", slug="queue", allow_public_submission=True
        )
        staff = User.objects.create(username="staff", is_staff=True, is_superuser=True)
        staff.set_password("pass")
        staff.save()
        self.client.login(username="staff", password="pass")
        self.client.post(
            "/tickets/submit/",
            {
                "queue": queue.id,
                "title": "no address given",
                "body": "body",
                "priority": 3,
                "submitter_email": "",
            },
            follow=True,
        )
        ticket = Ticket.objects.get(title="no address given")
        self.assertEqual(ticket.submitter_email, "")
