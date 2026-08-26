import uuid
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import Queue, Ticket

User = get_user_model()


class TicketModelTests(TestCase):
    """
    Test suite for the ticket model class.
    """

    @classmethod
    def setUpTestData(cls):
        # Alice works as support staff to resolve tickets
        cls.user = User.objects.create_user(
            username="alice", password="testpass123", is_staff=True
        )
        cls.queue = Queue.objects.create(title="Products", slug="products")
        cls.ticket = Ticket.objects.create(
            title="Product not received",
            submitter_email="bob@example.com",
            queue=cls.queue,
        )

    def test_str_representation(self):
        actual = str(self.ticket)
        expected = f"{self.ticket.id} {self.ticket.title}"

        self.assertEqual(actual, expected)

    def test_meta_options(self):
        meta = self.ticket._meta

        self.assertEqual(meta.ordering, ("id",))
        self.assertEqual(meta.verbose_name, "Ticket")
        self.assertEqual(meta.verbose_name_plural, "Tickets")
        self.assertEqual(meta.get_latest_by, "created")

    def test_get_absolute_url(self):
        actual = self.ticket.get_absolute_url()
        expected = reverse("helpdesk:view", kwargs={"ticket_id": self.ticket.id})

        self.assertEqual(actual, expected)

    def test_default_fields_generated_correctly(self):
        # Basic
        self.assertEqual(self.ticket.title, "Product not received")
        self.assertEqual(self.ticket.submitter_email, "bob@example.com")
        self.assertEqual(self.ticket.queue, self.queue)

        # default ticket is unassigned and open
        self.assertIsNone(self.ticket.assigned_to)
        self.assertEqual(self.ticket.status, Ticket.OPEN_STATUS)
        self.assertFalse(self.ticket.on_hold)

        # Priority
        self.assertEqual(self.ticket.priority, 3)  # normal priority is assigned

        # Secret key field
        self.assertIsNotNone(self.ticket.secret_key)
        self.assertEqual(len(self.ticket.secret_key), len(str(uuid.uuid4())))

        # Created & modified data
        now = timezone.now()
        created, modified = self.ticket.created, self.ticket.modified

        self.assertIsNotNone(self.ticket.created)
        self.assertEqual(created.day, now.day)
        self.assertEqual(created.hour, now.hour)
        self.assertEqual(created.minute, now.minute)
        self.assertEqual(created.second, now.second)

        self.assertIsNotNone(self.ticket.modified)
        self.assertEqual(modified.day, now.day)
        self.assertEqual(modified.hour, now.hour)
        self.assertEqual(modified.minute, now.minute)
        self.assertEqual(modified.second, now.second)

    def test_created_and_modified_fields_update_correctly(self):
        # Arrange
        # We'll add an description to the ticket and assign it to Alice
        self.ticket.assigned_to = self.user
        self.ticket.description = "Still awaiting my product"
        created, modified = self.ticket.created, self.ticket.modified

        # Act
        self.ticket.save()
        self.ticket.refresh_from_db()

        # Assert
        # Created should remain unchanged
        self.assertEqual(self.ticket.created, created)

        # Modified should update
        self.assertNotEqual(self.ticket.modified, modified)
        self.assertTrue(self.ticket.modified > self.ticket.created)

    def test_very_long_title_is_truncated(self):
        # Arrange: give a long title to a ticket
        self.ticket.title = "ABC" * 100
        self.ticket.save()

        self.ticket.refresh_from_db()

        self.assertEndsWith(self.ticket.title, "...")
        self.assertEqual(len(self.ticket.title), 200)

    def test_get_assigned_to_property(self):
        # current ticket is unassigned
        self.assertEqual(self.ticket.get_assigned_to, "Unassigned")

        # Alice takes up the ticket
        self.ticket.assigned_to = self.user
        self.ticket.save()
        self.ticket.refresh_from_db()

        self.assertEqual(self.ticket.get_assigned_to, self.user.get_username())

        # Alice updates her full name
        self.user.first_name = "Alice"
        self.user.last_name = "Wonderland"
        self.user.save()
        self.user.refresh_from_db()
        self.ticket.refresh_from_db()

        self.assertEqual(self.ticket.get_assigned_to, self.user.get_full_name())

    def test_ticket_subject_line_property(self):
        actual = self.ticket.ticket
        expected = f"[{self.ticket.queue.slug}-{self.ticket.id}]"

        self.assertEqual(actual, expected)

    def test_ticket_url_property(self):
        actual = self.ticket.ticket_for_url
        expected = f"{self.ticket.queue.slug}-{self.ticket.id}"

        self.assertEqual(actual, expected)

    def test_priority_css_class_property(self):
        # Our default priority is 3
        self.assertEqual(self.ticket.get_priority_css_class, "")

        # We make our ticket high priority
        self.ticket.priority = 1
        self.ticket.save()
        self.ticket.refresh_from_db()

        self.assertEqual(self.ticket.get_priority_css_class, "danger")

    def test_status_badge_class_property(self):
        # Our default status is open = 1
        self.assertEqual(self.ticket.get_status_badge_class, "danger")

    def test_priority_badge_class_property(self):
        # Our default priority is 3
        actual = self.ticket.get_priority_badge_class
        expected = self.ticket.PRIORITY_CSS_CLASSES.get(self.ticket.priority)

        self.assertEqual(actual, expected)

    def test_status_message(self):
        self.assertEqual(self.ticket.get_status, "Open")

    def test_full_domain_ticket_url_property(self):
        # Arrange
        from django.contrib.sites.models import Site

        domain = Site.objects.get_current().domain

        ticket_for_url = self.ticket.ticket_for_url
        email = self.ticket.submitter_email
        key = self.ticket.secret_key

        url = reverse("helpdesk:public_view")

        actual = self.ticket.ticket_url
        expected = (
            f"http://{domain}{url}?ticket={ticket_for_url}&email={email}&key={key}"
        )
        self.assertEqual(actual, expected)
