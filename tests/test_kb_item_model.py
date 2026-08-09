from django.test import TestCase
from django.urls import reverse

from helpdesk.models import KBCategory, KBItem, Queue, Ticket


class KBItemModelTests(TestCase):
    """
    Test suite for the KBItem Model.
    """

    @classmethod
    def setUpTestData(cls):
        cls.kb_category = KBCategory.objects.create(
            name="Accounts",
            title="Customer Accounts",
            slug="customer-accounts",
            description="Account access related problems",
        )
        cls.kbitem = KBItem.objects.create(
            category=cls.kb_category,
            title="Password",
            question="How to reset a password?",
            answer="Go to settings then click reset password.",
        )
        # Create two unassigned tickets for our kbitem
        # one open other closed
        cls.queue = Queue.objects.create(title="Accounts", slug="accounts")
        cls.open_ticket = Ticket.objects.create(
            title="Account locked",
            status=Ticket.OPEN_STATUS,
            queue=cls.queue,
            kbitem=cls.kbitem,
        )
        cls.closed_ticket = Ticket.objects.create(
            title="Account blocked",
            status=Ticket.CLOSED_STATUS,
            queue=cls.queue,
            kbitem=cls.kbitem,
        )

    def test_str_representation(self):
        actual = str(self.kbitem)
        expected = f"{self.kb_category.title}: {self.kbitem.title}"
        self.assertEqual(actual, expected)

    def test_verbose_names_and_ordering(self):
        meta = self.kbitem._meta
        self.assertEqual(meta.verbose_name, "Knowledge base item")
        self.assertEqual(meta.verbose_name_plural, "Knowledge base items")
        self.assertEqual(meta.ordering, ("order", "title"))

    def test_absolute_url(self):
        category_url = self.kbitem.category.get_absolute_url()
        expected = f"{category_url}?kbitem={self.kbitem.id}"

        actual = self.kbitem.get_absolute_url()

        self.assertEqual(actual, expected)

    def test_score_for_zero_votes_is_correctly_calculated(self):
        # by default we have zero votes
        self.assertEqual(self.kbitem.score, "Unrated")

    def test_score_for_low_recommendations(self):
        # Arrange
        recs, votes = 2, 25

        self.kbitem.recommendations = recs
        self.kbitem.votes = votes
        self.kbitem.save(update_fields=["votes", "recommendations"])
        self.kbitem.refresh_from_db()

        self.assertEqual(self.kbitem.score, 0.8)

    def test_score_for_high_recommendations(self):
        # Arrange
        recs, votes = 20, 25

        self.kbitem.recommendations = recs
        self.kbitem.votes = votes
        self.kbitem.save(update_fields=["votes", "recommendations"])
        self.kbitem.refresh_from_db()

        self.assertEqual(self.kbitem.score, 8)

    def test_query_url(self):
        actual = self.kbitem.query_url()
        expected = f"{reverse('helpdesk:list')}?kbitem={self.kbitem.id}"
        self.assertEqual(actual, expected)

    def test_num_open_tickets(self):
        self.assertEqual(Ticket.objects.count(), 2)
        self.assertEqual(self.kbitem.num_open_tickets(), 1)

    def test_unassigned_tickets(self):
        unassigned_tickets = self.kbitem.unassigned_tickets()
        self.assertIn(self.open_ticket, unassigned_tickets)
        self.assertNotIn(self.closed_ticket, unassigned_tickets)
