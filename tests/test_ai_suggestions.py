from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from helpdesk import settings as helpdesk_settings
from helpdesk.ai_suggestions import find_related_tickets
from helpdesk.models import Checklist, Queue, Ticket


@override_settings(HELPDESK_AI_ENABLED=True)
class AISuggestionTests(TestCase):
    def setUp(self):
        self.previous_queue_setting = (
            helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
        )
        helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = True
        self.addCleanup(self.restore_queue_setting)
        self.queue = Queue.objects.create(title="Support", slug="support")
        self.foreign_queue = Queue.objects.create(title="Private", slug="private")
        self.user = get_user_model().objects.create_user(
            username="agent", password="pass", is_staff=True
        )
        permission = Permission.objects.get(
            codename=self.queue.permission_name.removeprefix("helpdesk.")
        )
        self.user.user_permissions.add(permission)
        self.ticket = Ticket.objects.create(
            title="打印机无法连接",
            description="办公区打印机连接失败",
            queue=self.queue,
        )
        self.related = Ticket.objects.create(
            title="打印机连接失败",
            description="办公区打印机无法连接",
            resolution="检查网络连接",
            status=Ticket.RESOLVED_STATUS,
            queue=self.queue,
        )
        self.foreign = Ticket.objects.create(
            title="打印机连接失败 私密",
            description="办公区打印机无法连接",
            resolution="内部凭据 123",
            status=Ticket.RESOLVED_STATUS,
            queue=self.foreign_queue,
        )
        self.url = reverse("helpdesk:view", args=[self.ticket.id])
        self.client.force_login(self.user)

    def restore_queue_setting(self):
        helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = (
            self.previous_queue_setting
        )

    def test_retrieval_obeys_ticket_permissions(self):
        results = find_related_tickets(self.ticket, self.user)
        self.assertEqual([item.ticket.id for item in results], [self.related.id])

    def test_weak_overlap_does_not_appear_as_related(self):
        unrelated = Ticket.objects.create(
            title="办公区空调无法制冷",
            description="空调启动后没有冷风",
            resolution="检查制冷设备",
            status=Ticket.RESOLVED_STATUS,
            queue=self.queue,
        )
        results = find_related_tickets(self.ticket, self.user)
        self.assertNotIn(unrelated.id, [item.ticket.id for item in results])

    @patch("helpdesk.views.staff.generate_suggestion")
    def test_get_does_not_call_provider(self, generate):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        generate.assert_not_called()

    @override_settings(HELPDESK_AI_ENABLED=False)
    def test_feature_is_disabled_by_default(self):
        self.assertEqual(
            self.client.post(self.url, {"ai_suggest": "1"}).status_code, 404
        )

    @patch("helpdesk.views.staff.generate_suggestion")
    def test_existing_checklist_post_still_works(self, generate):
        response = self.client.post(self.url, {"name": "Review"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Checklist.objects.filter(ticket=self.ticket, name="Review").exists()
        )
        generate.assert_not_called()

    @patch("helpdesk.ai_suggestions.requests.post")
    @override_settings(
        HELPDESK_AI_CHAT_COMPLETIONS_URL="http://model.local/v1/chat/completions",
        HELPDESK_AI_MODEL="test-model",
    )
    def test_suggestion_shows_evidence_without_mutating_ticket(self, post):
        post.return_value = Mock(
            json=lambda: {"choices": [{"message": {"content": "先检查网络连接。"}}]}
        )
        before = (self.ticket.status, self.ticket.priority, self.ticket.assigned_to_id)
        response = self.client.post(self.url, {"ai_suggest": "1", "name": "Review"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "先检查网络连接。")
        self.assertContains(response, self.related.title)
        self.assertNotContains(response, self.foreign.title)
        payload = post.call_args.kwargs["json"]
        self.assertIn(str(self.related.id), payload["messages"][1]["content"])
        self.assertNotIn("内部凭据 123", payload["messages"][1]["content"])
        self.ticket.refresh_from_db()
        self.assertEqual(
            (self.ticket.status, self.ticket.priority, self.ticket.assigned_to_id),
            before,
        )
        self.assertEqual(Checklist.objects.count(), 0)

    @patch("helpdesk.ai_suggestions.requests.post")
    @override_settings(
        HELPDESK_AI_CHAT_COMPLETIONS_URL="http://model.local/v1/chat/completions",
        HELPDESK_AI_MODEL="test-model",
        HELPDESK_AI_REASONING_EFFORT="none",
        HELPDESK_AI_TIMEOUT_SECONDS=30,
    )
    def test_optional_provider_controls_are_forwarded(self, post):
        post.return_value = Mock(
            json=lambda: {"choices": [{"message": {"content": "Review evidence."}}]}
        )
        self.client.post(self.url, {"ai_suggest": "1"})
        self.assertEqual(post.call_args.kwargs["timeout"], 30)
        self.assertEqual(post.call_args.kwargs["json"]["reasoning_effort"], "none")

    @patch("helpdesk.ai_suggestions.requests.post")
    @override_settings(
        HELPDESK_AI_CHAT_COMPLETIONS_URL="http://model.local/v1/chat/completions",
        HELPDESK_AI_MODEL="test-model",
    )
    def test_foreign_ticket_is_rejected_before_model_call(self, post):
        url = reverse("helpdesk:view", args=[self.foreign.id])
        self.assertEqual(self.client.post(url, {"ai_suggest": "1"}).status_code, 302)
        post.assert_not_called()

    def test_unconfigured_provider_preserves_retrieval_and_ticket(self):
        response = self.client.post(self.url, {"ai_suggest": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "provider is unavailable")
        self.assertContains(response, self.related.title)

    @patch("helpdesk.ai_suggestions.requests.post")
    @override_settings(
        HELPDESK_AI_CHAT_COMPLETIONS_URL="http://model.local/v1/chat/completions",
        HELPDESK_AI_MODEL="test-model",
    )
    def test_model_html_is_escaped(self, post):
        post.return_value = Mock(
            json=lambda: {
                "choices": [{"message": {"content": "<script>alert(1)</script>"}}]
            }
        )
        response = self.client.post(self.url, {"ai_suggest": "1"})
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_anonymous_user_cannot_request_suggestion(self):
        self.client.logout()
        response = self.client.post(self.url, {"ai_suggest": "1"})
        self.assertNotEqual(response.status_code, 200)

    @patch("helpdesk.ai_suggestions.requests.post")
    @override_settings(
        HELPDESK_AI_CHAT_COMPLETIONS_URL="http://model.local/v1/chat/completions",
        HELPDESK_AI_MODEL="test-model",
    )
    def test_model_failure_does_not_change_ticket(self, post):
        post.side_effect = __import__("requests").Timeout()
        response = self.client.post(self.url, {"ai_suggest": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "provider is unavailable")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.OPEN_STATUS)
