from http import HTTPStatus

from django.test import TestCase
from django.urls import resolve, reverse

from helpdesk.models import KBCategory, Queue, Ticket

from .helpers import get_staff_user


class KBIndexViewTests(TestCase):
    """
    Test suite for the Knowledge base index view. This serves as the home page
    for the knowledge base section showing all categories to browse.
    """

    @classmethod
    def setUpTestData(cls):
        cls.template = "helpdesk/kb_index.html"
        cls.url = reverse("helpdesk:kb_index")
        cls.user = get_staff_user()
        # We create a queue and its companion public, private kb category
        cls.queue = Queue.objects.create(
            title="Accounts",
            slug="accounts",
        )
        cls.kb_category1 = KBCategory.objects.create(
            title="Customer Accounts",
            slug="customer-accounts",
            description="Account access related problems",
            queue=cls.queue,
            public=True,
        )
        cls.kb_category2 = KBCategory.objects.create(
            title="Account blocked",
            slug="account-blocked",
            description="Account blocked related problems",
            queue=cls.queue,
            public=False,  # <- Note
        )

    def test_url_resolves_correct_view(self):
        match = resolve(self.url)
        self.assertEqual(match.url_name, "kb_index")

    def test_anonymous_user_can_access(self):
        # Act
        r = self.client.get(reverse("helpdesk:kb_index"))

        # Assert: check access
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, self.template)

        self.assertContains(r, self.kb_category1.title)
        self.assertNotContains(r, "Hi I shouldn't be on this page")
        self.assertContains(r, "View articles")

        # Assert: private category is not visible
        self.assertIn(self.kb_category1, r.context["kb_categories"])
        self.assertNotIn(self.kb_category2, r.context["kb_categories"])
        self.assertEqual(len(r.context["kb_categories"]), 1)
