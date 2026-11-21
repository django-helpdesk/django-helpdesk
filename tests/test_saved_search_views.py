from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import SavedSearch

from .helpers import get_staff_user


class SavedSearchViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_staff_user()
        cls.other_user = get_user_model().objects.create_user(
            username="other-saved-search-user",
            email="other@example.com",
            password="test-password",
            is_staff=True,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_save_query_creates_shared_search(self):
        response = self.client.post(
            reverse("helpdesk:savequery"),
            {
                "title": "Urgent tickets",
                "query_encoded": "encoded-query",
                "shared": "on",
            },
        )

        saved = SavedSearch.objects.get(title="Urgent tickets")
        self.assertEqual(saved.user, self.user)
        self.assertEqual(saved.query, "encoded-query")
        self.assertTrue(saved.shared)
        self.assertRedirects(
            response,
            f"{reverse('helpdesk:list')}?saved_query={saved.pk}",
            fetch_redirect_response=False,
        )

    def test_save_query_requires_title_and_query(self):
        for data in (
            {"query_encoded": "encoded-query"},
            {"title": "Missing query"},
        ):
            with self.subTest(data=data):
                response = self.client.post(reverse("helpdesk:savequery"), data)
                self.assertEqual(response.status_code, HTTPStatus.FOUND)
                self.assertEqual(response.url, reverse("helpdesk:list"))

        self.assertFalse(SavedSearch.objects.exists())

    def test_delete_query_requires_ownership_and_confirmation(self):
        owned = SavedSearch.objects.create(
            user=self.user, title="Mine", query="encoded-query"
        )
        foreign = SavedSearch.objects.create(
            user=self.other_user, title="Theirs", query="encoded-query"
        )

        url = reverse("helpdesk:delete_query", args=[owned.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "helpdesk/confirm_delete_saved_query.html")
        self.assertTrue(SavedSearch.objects.filter(pk=owned.pk).exists())

        foreign_url = reverse("helpdesk:delete_query", args=[foreign.pk])
        self.assertEqual(
            self.client.post(foreign_url).status_code, HTTPStatus.NOT_FOUND
        )

        response = self.client.post(url)
        self.assertRedirects(
            response, reverse("helpdesk:list"), fetch_redirect_response=False
        )
        self.assertFalse(SavedSearch.objects.filter(pk=owned.pk).exists())
        self.assertTrue(SavedSearch.objects.filter(pk=foreign.pk).exists())
