from django.test import TestCase

from helpdesk.lib import build_base_url

from django.contrib.sites.models import Site


class HelperTests(TestCase):
    """
    Test suite for verifying the correct functionality of helper
    methods defined in lib.py
    """

    def test_build_base_url_for_pre_configured_site(self):
        # Arrange:
        # Django test sets up a default site with pk=1 and domain as example.com

        domain = Site.objects.get_current().domain

        # Act
        actual = build_base_url()
        expected = f"http://{domain}"

        # Assert
        self.assertEqual(actual, expected)

    def test_build_base_url_for_no_configured_site(self):
        # Arrange: we delete the pre configured site by django
        Site.objects.all().delete()

        # Act
        actual = build_base_url()

        # Assert
        expected = "http://configure-django-sites.com"
        self.assertEqual(actual, expected)
