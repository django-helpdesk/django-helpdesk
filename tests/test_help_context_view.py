from http import HTTPStatus

from django.test import TestCase
from django.urls import resolve, reverse
from django.views.generic import TemplateView


class HelpContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("helpdesk:help_context")
        cls.template = "helpdesk/help_context.html"
        cls.base = "helpdesk/base.html"

    def test_url_resolves_correct_view(self):
        match = resolve(self.url)
        self.assertEqual(match.url_name, "help_context")
        self.assertEqual(match.func.view_class, TemplateView)

    def test_template_is_accessible(self):
        # Act
        r = self.client.get(self.url)

        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, self.template)
        self.assertTemplateUsed(r, self.base)
