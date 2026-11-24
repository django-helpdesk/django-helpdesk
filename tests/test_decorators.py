from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from helpdesk.decorators import (
    check_staff_status,
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
