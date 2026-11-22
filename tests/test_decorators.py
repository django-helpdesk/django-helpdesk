from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase

from helpdesk import settings as helpdesk_settings
from helpdesk.decorators import (
    check_staff_status,
    staff_member_required,
    superuser_required,
)


class DecoratorCoverageTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = lambda request: HttpResponse("allowed")

    def test_superuser_checker_rejects_inactive_user(self):
        user = mock.Mock(
            is_authenticated=True,
            is_active=False,
            is_superuser=True,
        )
        self.assertFalse(check_staff_status(False)(True)(user))

    def test_staff_decorator_redirects_anonymous_user(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        response = staff_member_required(self.view)(request)

        self.assertEqual(response.status_code, 302)

    def test_staff_decorator_rejects_non_staff_user(self):
        request = self.factory.get("/")
        request.user = mock.Mock(
            is_authenticated=True,
            is_active=True,
            is_staff=False,
        )

        with (
            mock.patch.object(
                helpdesk_settings,
                "HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE",
                False,
            ),
            self.assertRaises(PermissionDenied),
        ):
            staff_member_required(self.view)(request)

    def test_staff_decorator_uses_custom_protector(self):
        request = self.factory.get("/")
        request.user = mock.Mock(
            is_authenticated=True,
            is_active=True,
            is_staff=True,
        )
        redirect = HttpResponseRedirect("/protected/")

        with mock.patch.object(
            helpdesk_settings,
            "HELPDESK_STAFF_VIEW_PROTECTOR",
            return_value=redirect,
        ):
            response = staff_member_required(self.view)(request)

        self.assertIs(response, redirect)

    def test_staff_decorator_allows_valid_staff_user(self):
        request = self.factory.get("/")
        request.user = mock.Mock(
            is_authenticated=True,
            is_active=True,
            is_staff=True,
        )

        response = staff_member_required(self.view)(request)

        self.assertEqual(response.status_code, 200)

    def test_superuser_decorator_redirects_anonymous_user(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        response = superuser_required(self.view)(request)

        self.assertEqual(response.status_code, 302)

    def test_superuser_decorator_rejects_non_superuser(self):
        request = self.factory.get("/")
        request.user = mock.Mock(
            is_authenticated=True,
            is_active=True,
            is_superuser=False,
        )

        with self.assertRaises(PermissionDenied):
            superuser_required(self.view)(request)

    def test_superuser_decorator_allows_superuser(self):
        request = self.factory.get("/")
        request.user = mock.Mock(
            is_authenticated=True,
            is_active=True,
            is_superuser=True,
        )

        response = superuser_required(self.view)(request)

        self.assertEqual(response.status_code, 200)
