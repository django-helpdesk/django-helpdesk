import logging
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from helpdesk import settings as helpdesk_settings
from helpdesk.models import Queue, Ticket
from helpdesk.forms import TicketForm
from helpdesk.views.staff import get_user_queues
from helpdesk.update_ticket import update_ticket

User = get_user_model()


class TicketEmailNotificationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def setUp(self):
        # Need at least 2 public queues so that the queue_choices list contains a blank 1st entry
        self.queue_public_1 = Queue.objects.create(
            title="Public Queue 1",
            slug="public_queue_1",
            allow_public_submission=True,
        )
        self.queue_public_2 = Queue.objects.create(
            title="Public Queue 2",
            slug="public_queue_2",
            allow_public_submission=True,
        )
        self.queue_not_public_1 = Queue.objects.create(
            title="Not Public Queue",
            slug="not_public_queue",
            allow_public_submission=False,
        )
        self.logger = logging.getLogger("helpdesk")
        self.assigned_user = User.objects.create(
            username="asgnd_user",
            email="asgnd@djangohelpdesk.com",
        )
        self.creator_user = User.objects.create(
            username="create_user",
            email="create@djangohelpdesk.com",
        )
        self.new_ticket_cc_user = User.objects.create(
            username="new_ticket_cc_user",
            email="new_cc@djangohelpdesk.com",
        )
        self.update_ticket_cc_user = User.objects.create(
            username="update_ticket_cc_user",
            email="update_cc@djangohelpdesk.com",
        )
        self.update_user = User.objects.create(
            username="update_user",
            email="update@djangohelpdesk.com",
        )
        self.non_user_submitter_email = "submit@random.email"
        self.queue_choices = get_user_queues(self.creator_user)
        form = TicketForm(
            queue_choices=self.queue_choices,
            data={
                "title": "Existing Test Ticket",
                "body": "Test ticket update email notifications",
                "queue": self.queue_public_2.id,
                "submitter_email": self.non_user_submitter_email,
            },
        )
        form.full_clean()
        self.existing_ticket: Ticket = form.save(user=self.creator_user)
        self.outbox = mail.outbox  # @UndefinedVariable
        self.outbox.clear()  # Make sure the outbox is cleared for each test

    def test_create_ticket_assigned(self):
        """
        Ensure the appropriate roles are notified by email when new tickets are created
        """
        form = TicketForm(
            queue_choices=self.queue_choices,
            data={
                "title": "Test Ticket",
                "body": "Test email notifications",
                "queue": self.queue_public_2.id,
                "assigned_to": self.assigned_user.id,
                "submitter_email": self.non_user_submitter_email,
            },
        )
        form.full_clean()
        ticket: Ticket = form.save(user=self.creator_user)
        email_cnt = len(self.outbox)
        recipient_list = [email.to[0] for email in self.outbox]
        self.assertEqual(
            email_cnt,
            2,
            f"Expected to send 2 email notifications. {email_cnt} were sent.",
        )
        self.assertTrue(
            ticket.submitter_email in recipient_list,
            "Submitter email not found in email notifications sent.",
        )
        self.assertTrue(
            self.assigned_user.email in recipient_list,
            "Ticket assigned user email not found in email notifications sent.",
        )

    def test_create_ticket_not_assigned(self):
        """
        No explicit assignment of the ticket - system should assign ticket creator
        Use an actual user for submitter
        """
        form = TicketForm(
            queue_choices=self.queue_choices,
            data={
                "title": "Test Ticket",
                "body": "Test email notifications",
                "queue": self.queue_public_2.id,
                "submitter_email": self.creator_user.email,
            },
        )
        form.full_clean()
        ticket: Ticket = form.save(user=self.creator_user)
        email_cnt = len(self.outbox)
        recipient_list = [email.to[0] for email in self.outbox]
        self.assertEqual(
            email_cnt,
            1,
            f"Expected to send 1 email notification. {email_cnt} were sent.",
        )
        self.assertTrue(
            ticket.submitter_email in recipient_list,
            "Submitter email not found in email notifications sent.",
        )

    def test_update_ticket_default_behaviour(self):
        """
        Ticket is initially unassigned so should not get assigned email until assigned.
        Change various data points checking where submitter should get emailed.
        """
        # Ensure the attribute is correct since it is not reset on each test
        setattr(
            helpdesk_settings, "HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES", False
        )
        update_ticket(
            self.update_user,
            self.existing_ticket,
            comment="Should get a submitter email with this in update.",
            public=True,
        )
        email_cnt = len(self.outbox)
        recipient_list = [email.to[0] for email in self.outbox]
        self.assertEqual(
            email_cnt,
            1,
            f"1. Expected to send 1 email notification. {email_cnt} were sent: {recipient_list}",
        )
        self.assertTrue(
            self.existing_ticket.submitter_email in recipient_list,
            "Submitter email not found in email notifications sent.",
        )

        # Assign a user but no other change so submitter should be emailed.
        self.outbox.clear()  # Remove the prior emails
        update_ticket(
            self.update_user,
            self.existing_ticket,
            owner=self.assigned_user.id,
            public=True,
        )
        email_cnt = len(self.outbox)
        recipient_list = [email.to[0] for email in self.outbox]
        self.assertEqual(
            email_cnt,
            1,
            f"2. Expected to send 1 email notification. {email_cnt} were sent: {recipient_list}",
        )
        self.assertTrue(
            self.assigned_user.email in recipient_list,
            "Ticket assigned user email not found in email notifications sent.",
        )

        # Update the ticket status to REOPENED so submitter should not be emailed.
        self.outbox.clear()  # Remove the prior emails
        update_ticket(
            self.update_user,
            self.existing_ticket,
            new_status=Ticket.REOPENED_STATUS,
            public=True,
        )
        email_cnt = len(self.outbox)
        recipient_list = [email.to[0] for email in self.outbox]
        self.assertEqual(
            email_cnt,
            1,
            f"3. Expected to send 1 email notification. {email_cnt} were sent: {recipient_list}",
        )
        self.assertTrue(
            self.assigned_user.email in recipient_list,
            "Ticket assigned user email not found in email notifications sent.",
        )

        # Update the ticket status to CLOSED so submitter should be emailed.
        self.outbox.clear()  # Remove the prior emails
        update_ticket(
            self.update_user,
            self.existing_ticket,
            new_status=Ticket.CLOSED_STATUS,
            public=True,
        )
        email_cnt = len(self.outbox)
        recipient_list = [email.to[0] for email in self.outbox]
        self.assertEqual(
            email_cnt,
            2,
            f"4. Expected to send 2 email notifications. {email_cnt} were sent: {recipient_list}",
        )
        self.assertTrue(
            self.existing_ticket.submitter_email in recipient_list,
            "Submitter email not found in email notifications sent.",
        )
        self.assertTrue(
            self.assigned_user.email in recipient_list,
            "Ticket assigned user email not found in email notifications sent.",
        )

    def test_update_ticket_always_notify_submitter(self):
        """
        Ticket is initially unassigned so should not get assigned email until assigned.
        Check submitter should always get emailed.
        """
        # Ensure the attribute is correct since it is not reset on each test
        setattr(
            helpdesk_settings, "HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES", True
        )
        update_ticket(
            self.update_user,
            self.existing_ticket,
            comment="Should get a submitter email with this in update.",
            public=True,
        )
        email_cnt = len(self.outbox)
        recipient_list = [email.to[0] for email in self.outbox]
        self.assertEqual(
            email_cnt,
            1,
            f"1. Expected to send 1 email notification. {email_cnt} were sent: {recipient_list}",
        )
        self.assertTrue(
            self.existing_ticket.submitter_email in recipient_list,
            "Submitter email not found in email notifications sent.",
        )

        # Assign a user but no other change so submitter should not be emailed.
        self.outbox.clear()  # Remove the prior emails
        update_ticket(
            self.update_user,
            self.existing_ticket,
            owner=self.assigned_user.id,
            public=True,
        )
        email_cnt = len(self.outbox)
        recipient_list = [email.to[0] for email in self.outbox]
        self.assertEqual(
            email_cnt,
            2,
            f"2. Expected to send 2 email notifications. {email_cnt} were sent: {recipient_list}",
        )
        self.assertTrue(
            self.existing_ticket.submitter_email in recipient_list,
            "Submitter email not found in email notifications sent.",
        )
        self.assertTrue(
            self.assigned_user.email in recipient_list,
            "Ticket assigned user email not found in email notifications sent.",
        )

        # Update the ticket status to REOPENED - submitter should be emailed.
        self.outbox.clear()  # Remove the prior emails
        update_ticket(
            self.update_user,
            self.existing_ticket,
            new_status=Ticket.REOPENED_STATUS,
            public=True,
        )
        email_cnt = len(self.outbox)
        recipient_list = [email.to[0] for email in self.outbox]
        self.assertEqual(
            email_cnt,
            2,
            f"3. Expected to send 2 email notifications. {email_cnt} were sent: {recipient_list}",
        )
        self.assertTrue(
            self.existing_ticket.submitter_email in recipient_list,
            "Submitter email not found in email notifications sent.",
        )
        self.assertTrue(
            self.assigned_user.email in recipient_list,
            "Ticket assigned user email not found in email notifications sent.",
        )

        # Update the ticket status to CLOSED - submitter should be emailed.
        self.outbox.clear()  # Remove the prior emails
        update_ticket(
            self.update_user,
            self.existing_ticket,
            new_status=Ticket.CLOSED_STATUS,
            public=True,
        )
        email_cnt = len(self.outbox)
        recipient_list = [email.to[0] for email in self.outbox]
        self.assertEqual(
            email_cnt,
            2,
            f"4. Expected to send 2 email notifications. {email_cnt} were sent: {recipient_list}",
        )
        self.assertTrue(
            self.existing_ticket.submitter_email in recipient_list,
            "Submitter email not found in email notifications sent.",
        )
        self.assertTrue(
            self.assigned_user.email in recipient_list,
            "Ticket assigned user email not found in email notifications sent.",
        )

    def test_ticket_notifiy_cc(self):
        """
        Add CC user(s) to the queue for new tickets and updates.

        NOTE: Oddly the CC user for updates is also sent an email on create
        """
        # Ensure the attribute is correct since it is not reset on each test
        setattr(
            helpdesk_settings, "HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES", False
        )
        queue_id = self.queue_public_2.id
        queue = Queue.objects.get(id=queue_id)
        queue.enable_notifications_on_email_events = True
        queue.new_ticket_cc = self.new_ticket_cc_user.email
        queue.updated_ticket_cc = self.update_ticket_cc_user.email
        queue.save()
        form = TicketForm(
            queue_choices=self.queue_choices,
            data={
                "title": "Test Ticket",
                "body": "Test email notifications",
                "queue": self.queue_public_2.id,
                "assigned_to": self.assigned_user.id,
                "submitter_email": self.non_user_submitter_email,
            },
        )
        form.full_clean()
        ticket: Ticket = form.save(user=self.creator_user)
        email_cnt = len(self.outbox)
        recipient_list = [email.to[0] for email in self.outbox]
        self.assertEqual(
            email_cnt,
            4,
            f"New ticket CC Notifications test expected to send 4 email notifications. {email_cnt} were sent: {recipient_list}",
        )
        self.assertTrue(
            self.new_ticket_cc_user.email in recipient_list,
            "New ticket CC user email not found in email notifications sent.",
        )
        self.assertTrue(
            self.update_ticket_cc_user.email in recipient_list,
            "Update ticket CC user email not found in email notifications sent.",
        )
        self.assertTrue(
            self.assigned_user.email in recipient_list,
            "New ticket assigned user email not found in email notifications sent.",
        )
        self.assertTrue(
            ticket.submitter_email in recipient_list,
            "Submitter email not found in email notifications sent.",
        )

        # Update the ticket status to CLOSED.
        self.outbox.clear()  # Remove the prior emails
        update_ticket(
            self.update_user,
            ticket,
            new_status=Ticket.CLOSED_STATUS,
            public=True,
        )
        email_cnt = len(self.outbox)
        recipient_list = [email.to[0] for email in self.outbox]
        self.assertTrue(
            self.update_ticket_cc_user.email in recipient_list,
            "Updated ticket CC user email not found in email notifications sent.",
        )
        self.assertEqual(
            email_cnt,
            3,
            f"Updated CC Ticket test expected to send 3 email notifications. {email_cnt} were sent: {recipient_list}",
        )
        self.assertTrue(
            self.update_ticket_cc_user.email in recipient_list,
            "Update ticket CC user email not found in email notifications sent.",
        )
        self.assertTrue(
            self.assigned_user.email in recipient_list,
            "Ticket assigned user email not found in email notifications sent.",
        )
        self.assertTrue(
            ticket.submitter_email in recipient_list,
            "Submitter email not found in email notifications sent.",
        )

    def test_private_followup_default_behavior_no_submitter_emails(self):
        """Test that private follow-ups normally don't send submitter emails (existing behavior)."""
        # Ensure our new setting is disabled (default behavior) and HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES is False
        original_setting = getattr(
            helpdesk_settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", False
        )
        original_notify_all = getattr(
            helpdesk_settings, "HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES", False
        )
        setattr(helpdesk_settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", False)
        setattr(
            helpdesk_settings, "HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES", False
        )

        try:
            self.outbox.clear()  # Clear any existing emails
            update_ticket(
                user=self.update_user,
                ticket=self.existing_ticket,
                comment="This is a private comment",
                public=False,  # Private followup
            )

            email_cnt = len(self.outbox)
            # Private follow-ups don't send submitter emails by default (only to assigned users if they have email notifications enabled)
            # Since our test ticket is unassigned, no emails should be sent
            self.assertEqual(
                email_cnt,
                0,
                f"Expected 0 email notifications for private followup (existing behavior). {email_cnt} were sent.",
            )
        finally:
            # Restore original settings
            setattr(
                helpdesk_settings,
                "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS",
                original_setting,
            )
            setattr(
                helpdesk_settings,
                "HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES",
                original_notify_all,
            )

    def test_private_followup_no_emails_setting_enabled(self):
        """Test that private follow-ups don't send emails when HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS is True."""
        # Enable the setting
        original_setting = getattr(
            helpdesk_settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", False
        )
        setattr(helpdesk_settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", True)

        try:
            self.outbox.clear()  # Clear any existing emails
            update_ticket(
                user=self.update_user,
                ticket=self.existing_ticket,
                comment="This is a private comment",
                public=False,  # Private followup
            )

            email_cnt = len(self.outbox)
            self.assertEqual(
                email_cnt,
                0,
                f"Expected 0 email notifications for private followup when setting is enabled. {email_cnt} were sent.",
            )
        finally:
            # Restore original setting
            setattr(
                helpdesk_settings,
                "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS",
                original_setting,
            )

    def test_private_followup_setting_does_not_affect_public_followups(self):
        """Test that public follow-ups still send emails when HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS is True."""
        # Enable the setting
        original_setting = getattr(
            helpdesk_settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", False
        )
        setattr(helpdesk_settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", True)

        try:
            self.outbox.clear()  # Clear any existing emails
            update_ticket(
                user=self.update_user,
                ticket=self.existing_ticket,
                comment="This is a public comment",
                public=True,  # Public followup
            )

            email_cnt = len(self.outbox)
            self.assertGreater(
                email_cnt,
                0,
                "Expected email notifications for public followup even when private followup setting is enabled.",
            )

            # Verify submitter received email
            recipient_list = [email.to[0] for email in self.outbox]
            self.assertIn(
                self.existing_ticket.submitter_email,
                recipient_list,
                "Submitter should receive email for public followup.",
            )
        finally:
            # Restore original setting
            setattr(
                helpdesk_settings,
                "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS",
                original_setting,
            )

    def test_private_followup_setting_blocks_assigned_user_emails(self):
        """Test that HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS also blocks emails to assigned users."""
        # Enable the setting and assign a user to the ticket
        original_setting = getattr(
            helpdesk_settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", False
        )
        setattr(helpdesk_settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", True)

        try:
            # Assign ticket to a user first
            update_ticket(
                user=self.update_user,
                ticket=self.existing_ticket,
                owner=self.assigned_user.id,
                public=True,
            )
            self.outbox.clear()  # Clear assignment emails

            # Now make a private comment - normally this would email the assigned user
            update_ticket(
                user=self.update_user,
                ticket=self.existing_ticket,
                comment="This is a private comment for assigned user",
                public=False,  # Private followup
            )

            email_cnt = len(self.outbox)
            self.assertEqual(
                email_cnt,
                0,
                f"Expected 0 email notifications for private followup when setting is enabled. {email_cnt} were sent.",
            )
        finally:
            # Restore original setting
            setattr(
                helpdesk_settings,
                "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS",
                original_setting,
            )

    def test_private_followup_setting_blocks_notify_all_submitter_emails(self):
        """Test that HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS blocks emails when NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES is True."""
        # Enable both settings
        original_setting = getattr(
            helpdesk_settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", False
        )
        original_notify_all = getattr(
            helpdesk_settings, "HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES", False
        )
        setattr(helpdesk_settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", True)
        setattr(
            helpdesk_settings, "HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES", True
        )

        try:
            self.outbox.clear()  # Clear any existing emails
            update_ticket(
                user=self.update_user,
                ticket=self.existing_ticket,
                comment="This is a private comment",
                public=False,  # Private followup
            )

            email_cnt = len(self.outbox)
            # Even though NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES is True,
            # HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS should override it
            self.assertEqual(
                email_cnt,
                0,
                f"Expected 0 email notifications for private followup when setting is enabled, even with notify all enabled. {email_cnt} were sent.",
            )
        finally:
            # Restore original settings
            setattr(
                helpdesk_settings,
                "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS",
                original_setting,
            )
            setattr(
                helpdesk_settings,
                "HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES",
                original_notify_all,
            )

    def test_private_followup_setting_blocks_cc_user_emails(self):
        """Test that HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS also blocks emails to CC'd users."""
        from helpdesk.update_ticket import subscribe_to_ticket_updates

        # Enable the setting
        original_setting = getattr(
            helpdesk_settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", False
        )
        setattr(helpdesk_settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", True)

        try:
            # Add a CC user to the ticket
            cc_user = User.objects.create(
                username="cc_user",
                email="cc@djangohelpdesk.com",
            )
            subscribe_to_ticket_updates(
                ticket=self.existing_ticket, user_id=cc_user.id, can_view=True
            )

            self.outbox.clear()  # Clear any existing emails

            # Make a private comment - normally this would email CC'd users
            update_ticket(
                user=self.update_user,
                ticket=self.existing_ticket,
                comment="This is a private comment that CC users should not see",
                public=False,  # Private followup
            )

            email_cnt = len(self.outbox)
            self.assertEqual(
                email_cnt,
                0,
                f"Expected 0 email notifications for private followup when setting is enabled (including CC users). {email_cnt} were sent.",
            )
        finally:
            # Restore original setting
            setattr(
                helpdesk_settings,
                "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS",
                original_setting,
            )
