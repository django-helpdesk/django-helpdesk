import logging
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase

from helpdesk.email import create_ticket_cc
from helpdesk.models import Queue, Ticket


class EmailCCErrorTests(TestCase):
    def test_invalid_cc_subscription_does_not_block_other_recipients(self):
        queue = Queue.objects.create(title="Support", slug="support")
        ticket = Ticket.objects.create(
            title="Support request",
            queue=queue,
            submitter_email="sender@example.com",
        )
        logger = logging.getLogger("helpdesk")

        with mock.patch(
            "helpdesk.views.staff.subscribe_to_ticket_updates",
            side_effect=[ValidationError("Invalid CC"), "valid-subscription"],
        ) as subscribe:
            subscriptions = create_ticket_cc(
                ticket,
                [
                    ("", "invalid@example.com"),
                    ("", "valid@example.com"),
                ],
                logger,
            )

        self.assertEqual(subscriptions, ["valid-subscription"])
        self.assertEqual(subscribe.call_count, 2)

    def test_empty_cc_list_returns_no_subscriptions(self):
        queue = Queue.objects.create(title="Support", slug="support")
        ticket = Ticket.objects.create(
            title="Support request",
            queue=queue,
            submitter_email="sender@example.com",
        )

        result = create_ticket_cc(ticket, [], logging.getLogger("helpdesk"))

        self.assertEqual(result, [])

    def test_unlinked_cc_address_logs_warning_when_enabled(self):
        queue = Queue.objects.create(title="Support", slug="support")
        ticket = Ticket.objects.create(
            title="Support request",
            queue=queue,
            submitter_email="sender@example.com",
        )
        logger = mock.Mock(spec=logging.Logger)

        with (
            mock.patch(
                "helpdesk.email.helpdesk_settings.LOG_WARN_WHEN_CC_EMAIL_NOT_LINKED_TO_A_USER",
                True,
                create=True,
            ),
            mock.patch(
                "helpdesk.views.staff.subscribe_to_ticket_updates",
                return_value="subscription",
            ) as subscribe,
        ):
            result = create_ticket_cc(
                ticket,
                [("", "unknown@example.com")],
                logger,
            )

        self.assertEqual(result, ["subscription"])
        logger.warning.assert_called_once_with(
            "CC email address is not linked to an active user: unknown@example.com"
        )
        subscribe.assert_called_once_with(
            ticket=ticket,
            user_id=None,
            email="unknown@example.com",
        )
