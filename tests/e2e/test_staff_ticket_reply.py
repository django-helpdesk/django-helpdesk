import os
from typing import ClassVar
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from playwright.sync_api import expect, sync_playwright

from helpdesk import settings as helpdesk_settings
from helpdesk.models import Queue, Ticket, UserSettings


@override_settings(
    LANGUAGE_CODE="en-us",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class StaffTicketReplyTests(StaticLiveServerTestCase):
    fixtures: ClassVar[list[str]] = ["emailtemplate.json"]

    @classmethod
    def setUpClass(cls):
        # Updates must not call external or leftover webhook endpoints.
        cls.enterClassContext(
            patch.dict(
                os.environ,
                {
                    "HELPDESK_NEW_TICKET_WEBHOOK_URLS": "",
                    "HELPDESK_FOLLOWUP_WEBHOOK_URLS": "",
                },
            )
        )
        cls.enterClassContext(
            patch.object(helpdesk_settings, "HELPDESK_UPDATE_PUBLIC_DEFAULT", False)
        )
        super().setUpClass()

    def test_customer_sees_staff_public_reply_after_reload(self):
        password = "staff-test-password"
        staff = get_user_model().objects.create_user(
            username="support-agent",
            email="agent@example.com",
            password=password,
            is_staff=True,
        )
        user_settings = staff.usersettings_helpdesk
        user_settings.ticket_respond_layout = UserSettings.RESPOND_LAYOUT_TABS
        user_settings.save(update_fields=["ticket_respond_layout"])
        queue = Queue.objects.create(
            title="Customer Support",
            slug="customer-support",
            allow_public_submission=True,
        )
        ticket = Ticket.objects.create(
            queue=queue,
            title="Payment fails at checkout",
            description="The payment page displays an error after confirmation.",
            submitter_email="customer@example.com",
        )
        staff_url = self.live_server_url + ticket.get_absolute_url()
        public_url = self.live_server_url + ticket.ticket_url
        reply = "Please try again; we have restored the payment service."

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                staff_context = browser.new_context(locale="en-US")
                staff_page = staff_context.new_page()
                # Following the protected URL exercises the real login redirect.
                staff_page.goto(staff_url)
                staff_page.get_by_label("Username", exact=True).fill(staff.username)
                staff_page.get_by_label("Password", exact=True).fill(password)
                staff_page.get_by_role("button", name="Log in", exact=True).click()
                expect(staff_page).to_have_url(staff_url)

                staff_page.get_by_role("tab", name="Respond", exact=True).click()
                form = staff_page.locator("#ticket-respond-form")
                form.get_by_label("Comment / Resolution", exact=True).fill(reply)
                form.get_by_label(
                    "Is this update public? (Optional)", exact=True
                ).check()
                form.get_by_role("button", name="Save", exact=True).click()
                saved_reply = staff_page.locator("#followup-list").get_by_text(
                    reply, exact=True
                )
                expect(saved_reply).to_have_count(1)
                expect(saved_reply).to_be_visible()

                # A separate context cannot reuse the employee's authenticated session.
                customer_context = browser.new_context(locale="en-US")
                customer_page = customer_context.new_page()
                customer_page.goto(public_url)
                expect(
                    customer_page.get_by_role("heading", name=ticket.title, exact=True)
                ).to_be_visible()
                customer_reply = customer_page.locator("#followup-list").get_by_text(
                    reply, exact=True
                )
                expect(customer_reply).to_have_count(1)
                expect(customer_reply).to_be_visible()
                customer_page.reload()
                expect(customer_reply).to_have_count(1)
                expect(customer_reply).to_be_visible()
            finally:
                browser.close()

        # ORM checks run after Playwright's synchronous API has stopped.
        followup = ticket.followup_set.get()
        self.assertEqual(followup.comment, reply)
        self.assertEqual(followup.user_id, staff.pk)
        self.assertTrue(followup.public)
