from django.test import TestCase, override_settings
from django.urls import include, path, reverse

from .helpers import get_staff_user

# A host project that does not include django.conf.urls.i18n
urlpatterns = [
    path("", include("helpdesk.urls", namespace="helpdesk")),
]


class NavbarLanguageSwitcherTestCase(TestCase):
    def setUp(self):
        self.client.force_login(get_staff_user())

    def test_switcher_shown_with_i18n_urls(self):
        response = self.client.get(reverse("helpdesk:dashboard"))
        self.assertContains(response, f'action="{reverse("set_language")}"')

    @override_settings(ROOT_URLCONF=__name__)
    def test_staff_page_renders_without_i18n_urls(self):
        response = self.client.get(reverse("helpdesk:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="language"')

    @override_settings(ROOT_URLCONF=__name__)
    def test_public_page_renders_without_i18n_urls(self):
        self.client.logout()
        response = self.client.get(reverse("helpdesk:home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="language"')
