import sys
from datetime import datetime
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings

from helpdesk.lib import (
    build_base_url,
    daily_time_spent_calculation,
    get_assignable_users,
    process_attachments,
    queue_template_context,
    text_is_spam,
)


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


class TextIsSpamTests(SimpleTestCase):
    def setUp(self):
        self.request = Mock()
        self.request.META = {"REMOTE_ADDR": "192.0.2.10"}
        self.request.headers = {
            "User-Agent": "TestAgent",
            "Referer": "https://example.com/",
        }

    @patch.dict(sys.modules, {"akismet": ModuleType("akismet")})
    @patch("akismet.Akismet", create=True)
    @patch("django.contrib.sites.models.Site.objects.get_current")
    @override_settings(PYTHON_AKISMET_API_KEY="test-key")
    def test_verified_key_checks_comment(self, mock_site, mock_akismet):
        mock_site.return_value.domain = "example.com"
        mock_akismet.return_value.verify_key.return_value = True
        mock_akismet.return_value.comment_check.return_value = True

        self.assertTrue(text_is_spam("Spam message", self.request))

        mock_akismet.assert_called_once_with(
            blog_url="http://example.com/",
            key="test-key",
        )
        mock_akismet.return_value.comment_check.assert_called_once_with(
            "Spam message",
            data={
                "user_ip": "192.0.2.10",
                "user_agent": "TestAgent",
                "referrer": "https://example.com/",
                "comment_type": "comment",
                "comment_author": "",
            },
        )

    @patch.dict(sys.modules, {"akismet": ModuleType("akismet")})
    @patch("akismet.Akismet", create=True)
    @patch("django.contrib.sites.models.Site.objects.get_current")
    @override_settings(PYTHON_AKISMET_API_KEY="test-key")
    def test_invalid_key_returns_false(self, mock_site, mock_akismet):
        mock_site.return_value.domain = "example.com"
        mock_akismet.return_value.verify_key.return_value = False

        self.assertFalse(text_is_spam("Message", self.request))
        mock_akismet.return_value.comment_check.assert_not_called()

    @patch.dict(sys.modules, {"akismet": ModuleType("akismet")})
    @patch("akismet.Akismet", create=True)
    @patch("django.contrib.sites.models.Site.objects.get_current")
    @override_settings(TYPEPAD_ANTISPAM_API_KEY="typepad-key")
    def test_typepad_configuration(self, mock_site, mock_akismet):
        mock_site.return_value.domain = "example.com"
        mock_akismet.return_value.verify_key.return_value = False

        self.assertFalse(text_is_spam("Message", self.request))
        self.assertEqual(
            mock_akismet.return_value.baseurl,
            "api.antispam.typepad.com/1.1/",
        )

    @patch.dict(sys.modules, {"akismet": ModuleType("akismet")})
    @patch("akismet.Akismet", create=True)
    @patch("django.contrib.sites.models.Site.objects.get_current")
    @override_settings(AKISMET_API_KEY="legacy-key")
    def test_legacy_api_key(self, mock_site, mock_akismet):
        mock_site.return_value.domain = "example.com"
        mock_akismet.return_value.verify_key.return_value = False

        self.assertFalse(text_is_spam("Message", self.request))
        mock_akismet.assert_called_once_with(
            blog_url="http://example.com/",
            key="legacy-key",
        )

    @patch.dict(sys.modules, {"akismet": ModuleType("akismet")})
    @patch("django.contrib.sites.models.Site.objects.get_current")
    @override_settings(SITE_ID=None, PYTHON_AKISMET_API_KEY="test-key")
    def test_site_configuration_error_uses_fallback(self, mock_site):

        mock_site.side_effect = ImproperlyConfigured("Sites not configured")

        with patch("akismet.Akismet", create=True) as mock_akismet:
            mock_akismet.return_value.verify_key.return_value = False

            self.assertFalse(text_is_spam("Message", self.request))
            mock_akismet.assert_called_once_with(
                blog_url="http://configure-django-sites.com/",
                key="test-key",
            )

    @patch.dict(sys.modules, {"akismet": ModuleType("akismet")})
    @patch("akismet.Akismet", create=True)
    @patch("django.contrib.sites.models.Site.objects.get_current")
    def test_missing_api_key_returns_false(self, mock_site, mock_akismet):
        mock_site.return_value.domain = "example.com"

        self.assertFalse(text_is_spam("Message", self.request))
        mock_akismet.assert_not_called()


class QueueTemplateContextTests(SimpleTestCase):
    def test_callable_queue_attribute(self):
        queue = SimpleNamespace(
            title=lambda: "Support",
            slug="support",
            email_address="support@example.com",
            from_address="help@example.com",
            locale="en",
        )

        context = queue_template_context(queue)

        self.assertEqual(context["title"], "Support")
        self.assertEqual(context["slug"], "support")


class DailyTimeSpentTests(SimpleTestCase):
    def test_invalid_working_hours_raise_error(self):
        earliest = datetime(2026, 11, 23, 9, 0)
        latest = datetime(2026, 11, 23, 12, 0)

        with self.assertRaises(ImproperlyConfigured):
            daily_time_spent_calculation(
                earliest,
                latest,
                {"monday": (17, 9)},
            )

    def test_latest_time_before_opening(self):
        earliest = datetime(2026, 11, 23, 8, 0)
        latest = datetime(2026, 11, 23, 9, 0)

        result = daily_time_spent_calculation(
            earliest,
            latest,
            {"monday": (10, 17)},
        )

        self.assertEqual(result, 0)


class GetAssignableUsersTests(SimpleTestCase):
    @patch("helpdesk.lib.User.objects.filter")
    def test_filter_staff_users(self, mock_filter):
        active_users = MagicMock()
        staff_users = MagicMock()
        mock_filter.return_value = active_users
        active_users.filter.return_value = staff_users

        result = get_assignable_users(filter_staff=True)

        mock_filter.assert_called_once_with(is_active=True)
        active_users.filter.assert_called_once_with(is_staff=True)
        staff_users.order_by.assert_called_once()
        self.assertIs(result, staff_users.order_by.return_value)


class ProcessAttachmentsTests(SimpleTestCase):
    @patch("helpdesk.models.FollowUpAttachment")
    @override_settings(HELPDESK_MAX_EMAIL_ATTACHMENT_SIZE=100)
    def test_processes_multiple_attachments_including_empty_file(
        self, mock_attachment_model
    ):
        empty_file = SimpleNamespace(
            name="empty.txt", size=0, content_type="text/plain"
        )
        small_file = SimpleNamespace(
            name="small.txt", size=10, content_type="text/plain"
        )
        large_file = SimpleNamespace(
            name="large.txt", size=150, content_type="text/plain"
        )

        saved_files = []

        def create_attachment(**kwargs):
            attachment = MagicMock()
            attachment.file = kwargs["file"]
            saved_files.append(attachment)
            return attachment

        mock_attachment_model.side_effect = create_attachment

        result = process_attachments(
            followup=Mock(),
            attached_files=[empty_file, small_file, large_file],
        )

        self.assertEqual(result, [["small.txt", small_file]])
        self.assertEqual(mock_attachment_model.call_count, 2)

        for attachment in saved_files:
            attachment.full_clean.assert_called_once_with()
            attachment.save.assert_called_once_with()
