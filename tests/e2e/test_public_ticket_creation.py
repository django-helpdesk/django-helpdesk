import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from unittest.mock import patch
from urllib.parse import urljoin

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.formats import date_format
from playwright.sync_api import expect, sync_playwright

from helpdesk.models import FollowUpAttachment, Queue, Ticket


@override_settings(
    LANGUAGE_CODE="en-us",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PublicTicketCreationTests(StaticLiveServerTestCase):
    fixtures: ClassVar[list[str]] = ["emailtemplate.json"]

    @classmethod
    def setUpClass(cls):
        # Creation tests must not call external or leftover webhook endpoints.
        cls.enterClassContext(
            patch.dict(
                os.environ,
                {
                    "HELPDESK_NEW_TICKET_WEBHOOK_URLS": "",
                    "HELPDESK_FOLLOWUP_WEBHOOK_URLS": "",
                },
            )
        )
        # Isolate uploads and configure media serving before starting the server.
        media_directory = TemporaryDirectory(prefix="helpdesk-e2e-")
        cls.addClassCleanup(media_directory.cleanup)
        media_settings = override_settings(
            MEDIA_ROOT=media_directory.name,
            MEDIA_URL="/media/",
        )
        media_settings.enable()
        cls.addClassCleanup(media_settings.disable)
        super().setUpClass()

    def test_anonymous_user_creates_ticket_without_attachment(self):
        queue = Queue.objects.create(
            title="Customer Support",
            slug="customer-support",
            allow_public_submission=True,
        )
        title = "Payment fails at checkout"
        description = "Payment failed appears after confirming the order."
        email = "customer@example.com"

        with self._browser_page() as page:
            self._fill_ticket_form(
                page, queue=queue, email=email, title=title, description=description
            )
            page.get_by_role("button", name="Create Ticket", exact=True).click()
            self._assert_ticket_details(
                page, queue=queue, email=email, title=title, description=description
            )

        self._assert_saved_ticket(
            queue=queue, email=email, title=title, description=description
        )
        self.assertFalse(FollowUpAttachment.objects.exists())

    def test_anonymous_user_creates_ticket_with_image(self):
        queue = Queue.objects.create(
            title="Customer Support",
            slug="customer-support",
            allow_public_submission=True,
        )
        title = "Payment fails with an error screenshot"
        description = "The attached screenshot shows the payment error."
        email = "customer@example.com"
        image_path = Path(__file__).parent / "fixtures" / "ticket-attachment.png"
        image_bytes = image_path.read_bytes()

        with self._browser_page() as page:
            self._fill_ticket_form(
                page, queue=queue, email=email, title=title, description=description
            )
            page.get_by_label("Attach File", exact=True).set_input_files(
                str(image_path)
            )
            page.get_by_role("button", name="Create Ticket", exact=True).click()
            self._assert_ticket_details(
                page, queue=queue, email=email, title=title, description=description
            )

            attachment_link = page.get_by_role("link", name=image_path.name, exact=True)
            expect(attachment_link).to_have_count(1)
            expect(attachment_link).to_be_visible()
            expect(attachment_link).to_have_attribute("href", re.compile(r".+"))
            image_url = urljoin(page.url, attachment_link.get_attribute("href"))

            # Open the actual UI link and verify the served image bytes.
            with page.expect_response(image_url) as image_response:
                attachment_link.click()
            response = image_response.value
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["content-type"], "image/png")
            self.assertEqual(response.body(), image_bytes)

        ticket = self._assert_saved_ticket(
            queue=queue, email=email, title=title, description=description
        )

        attachment = FollowUpAttachment.objects.get(followup__ticket=ticket)
        self.assertEqual(attachment.filename, image_path.name)
        self.assertEqual(attachment.mime_type, "image/png")
        self.assertEqual(attachment.size, len(image_bytes))
        with attachment.file.open("rb") as uploaded_file:
            self.assertEqual(uploaded_file.read(), image_bytes)

    @override_settings(TIME_ZONE="UTC", USE_TZ=True)
    def test_anonymous_user_creates_ticket_with_priority_and_due_date(self):
        queue = Queue.objects.create(
            title="Customer Support",
            slug="customer-support",
            allow_public_submission=True,
        )
        title = "Payment issue needs attention before the deadline"
        description = "Please investigate the payment issue before the selected date."
        email = "customer@example.com"
        priority = 2
        # Keep the deadline in the future on every run, at midnight UTC.
        due_day = timezone.localdate() + timedelta(days=7)
        due_date_input = due_day.isoformat()
        expected_due_date = timezone.make_aware(datetime.combine(due_day, time.min))
        with translation.override("en-us"):
            displayed_due_date = date_format(expected_due_date, "DATETIME_FORMAT")

        with self._browser_page() as page:
            self._fill_ticket_form(
                page, queue=queue, email=email, title=title, description=description
            )
            page.get_by_label("Priority", exact=True).select_option(str(priority))
            page.get_by_label("Due on", exact=True).fill(due_date_input)
            page.get_by_role("button", name="Create Ticket", exact=True).click()

            ticket_details = self._assert_ticket_details(
                page, queue=queue, email=email, title=title, description=description
            )
            priority_details = ticket_details.locator(".col").filter(
                has=page.get_by_text("Priority", exact=True)
            )
            expect(priority_details).to_contain_text("2. High")
            due_date_details = ticket_details.locator(".col").filter(
                has=page.get_by_text("Due On", exact=True)
            )
            expect(due_date_details).to_contain_text(displayed_due_date)

        ticket = self._assert_saved_ticket(
            queue=queue, email=email, title=title, description=description
        )
        self.assertEqual(ticket.priority, priority)
        self.assertEqual(ticket.due_date, expected_due_date)

    def test_anonymous_user_corrects_missing_description_and_creates_ticket(self):
        queue = Queue.objects.create(
            title="Customer Support",
            slug="customer-support",
            allow_public_submission=True,
        )
        title = "Payment fails after confirming the order"
        description = "The payment page displays an error after confirmation."
        email = "customer@example.com"

        with self._browser_page() as page:
            self._fill_ticket_form(
                page, queue=queue, email=email, title=title, description=""
            )
            page.get_by_role("button", name="Create Ticket", exact=True).click()

            # Native required-field validation blocks submission before any POST.
            description_input = page.get_by_label(
                "Description of your issue", exact=True
            )
            expect(page).to_have_url(self.live_server_url + reverse("helpdesk:submit"))
            expect(description_input).to_be_empty()
            expect(description_input).to_be_focused()
            self.assertTrue(
                description_input.evaluate("field => field.validity.valueMissing")
            )
            self.assertTrue(
                description_input.evaluate("field => field.validationMessage")
            )

            expect(page.get_by_label("Queue", exact=True)).to_have_value(str(queue.pk))
            expect(page.get_by_label("Your E-Mail Address", exact=True)).to_have_value(
                email
            )
            expect(
                page.get_by_label("Summary of the problem", exact=True)
            ).to_have_value(title)

            # Query in a separate thread while Playwright's event loop is active.
            with ThreadPoolExecutor(max_workers=1) as executor:
                try:
                    self.assertEqual(executor.submit(Ticket.objects.count).result(), 0)
                finally:
                    executor.submit(connections.close_all).result()

            # Correct only the missing field; the retained values must be reused.
            description_input.fill(description)
            page.get_by_role("button", name="Create Ticket", exact=True).click()
            self._assert_ticket_details(
                page, queue=queue, email=email, title=title, description=description
            )

        # get() also rejects duplicate tickets after the two submission attempts.
        self._assert_saved_ticket(
            queue=queue, email=email, title=title, description=description
        )

    @contextmanager
    def _browser_page(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=os.environ.get("HEADED") != "1",
                slow_mo=int(os.environ.get("SLOW_MO", "0")),
            )
            try:
                # A fresh browser context has no authenticated session.
                context = browser.new_context(locale="en-US")
                yield context.new_page()
            finally:
                browser.close()

    def _fill_ticket_form(self, page, *, queue, email, title, description):
        page.goto(self.live_server_url + reverse("helpdesk:home"))
        page.get_by_role("link", name="Create a ticket", exact=True).click()
        page.get_by_label("Queue", exact=True).select_option(str(queue.pk))
        page.get_by_label("Your E-Mail Address", exact=True).fill(email)
        page.get_by_label("Summary of the problem", exact=True).fill(title)
        page.get_by_label("Description of your issue", exact=True).fill(description)

    def _assert_ticket_details(self, page, *, queue, email, title, description):
        view_url = self.live_server_url + reverse("helpdesk:public_view")
        expect(page).to_have_url(re.compile(rf"^{re.escape(view_url)}\?.+"))

        ticket_details = page.locator("#content-wrapper")
        expect(ticket_details).to_have_count(1)
        expect(ticket_details).to_be_visible()
        expect(
            ticket_details.get_by_role("heading", name=title, exact=True)
        ).to_be_visible()
        expect(ticket_details).to_contain_text(description)
        expect(ticket_details).to_contain_text(email)
        expect(ticket_details).to_contain_text(queue.title)
        return ticket_details

    def _assert_saved_ticket(self, *, queue, email, title, description):
        # Call only after Playwright stops so ORM access remains synchronous.
        ticket = Ticket.objects.get()
        self.assertEqual(ticket.title, title)
        self.assertEqual(ticket.description, description)
        self.assertEqual(ticket.submitter_email, email)
        self.assertEqual(ticket.queue_id, queue.pk)
        self.assertEqual(ticket.status, Ticket.OPEN_STATUS)
        return ticket
