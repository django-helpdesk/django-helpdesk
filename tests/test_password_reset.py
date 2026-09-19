from http import HTTPStatus

from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.test import TestCase
from django.urls import resolve, reverse


class PasswordResetTests(TestCase):
    """
    We use django's default auth views for password reset on custom endpoints
    using our own templates.

    So we don't have to test django's functionality here. We simply test the
    liveliness of our endpoints as a safety measure.
    """

    @classmethod
    def setUpTestData(cls):
        cls.uidb64 = "Nw"
        cls.token = "dew379-945dc641ba5ed9703cc3f35a557be9f7"

    # Password Reset
    def test_password_reset_url_resolves_correct_view(self):
        match = resolve(reverse("helpdesk:password_reset"))

        self.assertEqual(match.url_name, "password_reset")
        self.assertEqual(match.route, "password-reset/")
        self.assertEqual(match.func.view_class, PasswordResetView)

    def test_password_reset_url_works(self):
        r = self.client.get(reverse("helpdesk:password_reset"))

        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, "helpdesk/registration/password_reset_form.html")

    # Password Reset Done
    def test_password_reset_done_url_resolves_correct_view(self):
        match = resolve(reverse("helpdesk:password_reset_done"))

        self.assertEqual(match.url_name, "password_reset_done")
        self.assertEqual(match.route, "password-reset/done/")
        self.assertEqual(match.func.view_class, PasswordResetDoneView)

    def test_password_reset_done_page_works(self):
        r = self.client.get(reverse("helpdesk:password_reset_done"))

        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, "helpdesk/registration/password_reset_done.html")

    # Password Reset Confirm
    def test_password_reset_confirm_url_resolves_correct_view(self):
        match = resolve(
            reverse("helpdesk:password_reset_confirm", args=[self.uidb64, self.token])
        )

        self.assertEqual(match.url_name, "password_reset_confirm")
        self.assertEqual(match.func.view_class, PasswordResetConfirmView)

    def test_password_reset_confirm_page_works(self):
        r = self.client.get(
            reverse("helpdesk:password_reset_confirm", args=[self.uidb64, self.token])
        )

        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, "helpdesk/registration/password_reset_confirm.html")

    # Password Reset Complete
    def test_password_reset_complete_url_resolves_correct_view(self):
        match = resolve(reverse("helpdesk:password_reset_complete"))

        self.assertEqual(match.url_name, "password_reset_complete")
        self.assertEqual(match.route, "password-reset-complete/")
        self.assertEqual(match.func.view_class, PasswordResetCompleteView)

    def test_password_reset_complete_page_works(self):
        r = self.client.get(reverse("helpdesk:password_reset_complete"))

        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, "helpdesk/registration/password_reset_complete.html")
