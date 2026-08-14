from http import HTTPStatus

from django.test import TestCase
from django.urls import resolve, reverse

from helpdesk.models import KBCategory, KBItem

from .helpers import get_staff_user


class KBCategoryViewTests(TestCase):
    """
    Test suite for the KBCategory (detail) view which lists
    all questions & answers for a particular category.

    This page may be either rendered a a regular template or used
    as an iframe in another website.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = get_staff_user()
        cls.kb_category = KBCategory.objects.create(
            title="Customer Accounts",
            slug="customer-accounts",
            description="Account access related problems",
        )
        # Create two knowledge base items our kb category
        cls.kbitem1 = KBItem.objects.create(
            category=cls.kb_category,
            title="Password",
            question="How to reset a password?",
            answer="Go to settings then click reset password.",
        )
        cls.kbitem2 = KBItem.objects.create(
            category=cls.kb_category,
            title="Account Blocked",
            question="How to unblock customer account?",
            answer="Go to settings then click unblock account.",
        )

        cls.template = "helpdesk/kb_category.html"
        cls.iframe_template = "helpdesk/kb_category_iframe.html"

        kwargs = {"slug": cls.kb_category.slug}
        cls.url = reverse("helpdesk:kb_category", kwargs=kwargs)
        cls.iframe_url = reverse("helpdesk:kb_category_iframe", kwargs=kwargs)

    def test_url_resolves_correct_view(self):
        match = resolve(self.url)
        self.assertEqual(match.url_name, "kb_category")

    def test_anonymous_user_cannot_access_private_kb_category(self):
        # Arrange: Make our category private
        self.kb_category.public = False
        self.kb_category.save(update_fields=["public"])
        self.kb_category.refresh_from_db()
        # Make sure category is private
        self.assertFalse(self.kb_category.public)

        # Act: Anonymous users tries to access it
        r = self.client.get(self.url)

        # Assert
        self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)
        self.assertTemplateNotUsed(r, self.template)

    def test_kb_category_page_for_anonymous_user(self):
        # Act
        r = self.client.get(self.url)

        # Assert
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, self.template)
        self.assertContains(r, self.kb_category.title)
        self.assertContains(r, self.kb_category.description)
        self.assertContains(r, "Create New Ticket")

        # Check all kbitems are on page
        self.assertEqual(len(r.context["items"]), 2)
        self.assertContains(r, self.kbitem1.title)
        self.assertContains(r, self.kbitem1.question)
        self.assertContains(r, self.kbitem1.answer)

        self.assertContains(r, self.kbitem2.title)
        self.assertContains(r, self.kbitem2.question)
        self.assertContains(r, self.kbitem2.answer)

    def test_kb_category_page_for_staff_user(self):
        # Arrange: Staff user logs in
        self.client.force_login(self.user)

        # Act
        r = self.client.get(self.url)

        # Assert
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, self.template)
        self.assertContains(r, self.kb_category.title)
        self.assertContains(r, self.kb_category.description)
        self.assertContains(r, "Create New Ticket")

        # Staff user should see voting buttons
        upvote_url = f"/kb/{self.kbitem1.id}/vote/up/"
        downvote_url = f"/kb/{self.kbitem1.id}/vote/down/"

        self.assertContains(r, upvote_url)
        self.assertContains(r, downvote_url)

    # Iframe
    def test_kb_category_iframe_url_resolves_correct_view(self):
        match = resolve(self.iframe_url)
        self.assertEqual(match.url_name, "kb_category_iframe")

    def test_kb_category_iframe_render(self):
        # Act
        r = self.client.get(self.iframe_url)

        # Assert
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, self.iframe_template)
        self.assertContains(r, self.kb_category.title)
        self.assertContains(r, self.kb_category.description)
        self.assertContains(r, "Contact a human")
