from http import HTTPStatus
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from helpdesk.models import KBCategory, KBItem, Queue, SavedSearch, Ticket
from helpdesk.query import query_to_base64

User = get_user_model()


class StaffTicketListViewTests(TestCase):
    """
    Test suite for the internal staff ticket list view which holds the main
    Data table, timeline, filters and custom queries.
    """

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staffuser1", password="testpass123", is_staff=True
        )
        self.kb_category = KBCategory.objects.create(
            name="Payments",
            title="Payment related issues",
            slug="payments",
            description="All about payments",
        )
        self.kb_item = KBItem.objects.create(
            title="Tough clients",
            question="How to handle them?",
            answer="Show empathy",
            category=self.kb_category,
        )
        self.queue = Queue.objects.create(title="Payments", slug="payments")
        self.ticket = Ticket.objects.create(
            title="My card got double charged!",
            submitter_email="customer@example.com",
            queue=self.queue,
        )
        self.url = reverse("helpdesk:list")
        self.template = "helpdesk/ticket_list.html"
        self.default_params = {
            "filtering": {"status__in": [1, 2]},
            "sorting": "created",
            "search_string": "",
            "sortreverse": False,
        }

    def test_url_resolves_correct_view(self):
        match = resolve(self.url)
        self.assertEqual(match.url_name, "list")

    def test_anonymous_user_cannot_access(self):
        # Arrange
        login_url = "{}?next={}".format(reverse("helpdesk:login"), self.url)

        # Act
        # Make an anonymous user directly access the ticket detail url
        r = self.client.get(self.url)

        # Assert
        # User should be redirected to login screen
        self.assertEqual(r.status_code, HTTPStatus.FOUND)
        self.assertRedirects(r, login_url)
        self.assertTemplateNotUsed(r, self.template)

    def test_staff_user_can_access_ticket_list_page(self):
        # Arrange: staff user logs in
        self.client.force_login(self.staff_user)

        # Act
        r = self.client.get(self.url)

        # Assert
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, self.template)
        self.assertNotContains(r, "I should not be on this page")

        # Check data table buttons is displayed
        self.assertContains(r, "Actions")
        self.assertContains(r, "Filters")
        self.assertContains(r, "Columns")
        self.assertContains(r, "Timeline")

        # Check default query params are loaded
        self.assertEqual(r.context["query_params"], self.default_params)

    def test_sorting_dropdown_lists_all_sortable_columns(self):
        self.client.force_login(self.staff_user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, HTTPStatus.OK)
        for sort_value in (
            "id",
            "created",
            "last_followup",
            "due_date",
            "title",
            "queue",
            "status",
            "priority",
            "assigned_to",
            "submitter_email",
            "kbitem",
        ):
            self.assertContains(r, f"value='{sort_value}'")

    def test_sort_last_followup_is_accepted_and_selected(self):
        self.client.force_login(self.staff_user)
        r = self.client.get(self.url, data={"sort": "last_followup"})
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.context["query_params"]["sorting"], "last_followup")
        self.assertContains(
            r,
            "<option value='last_followup' selected='selected'>",
            html=False,
        )

    def test_user_saved_queries_executed_correctly(self):
        # Arrange: We create a public saved query for the user
        query = query_to_base64(self.default_params)
        ss = SavedSearch.objects.create(
            title="Password related tickets",
            shared=True,
            query=query,
            user=self.staff_user,
        )
        self.client.force_login(self.staff_user)

        # Act: Staff user loads a saved query
        r = self.client.get(self.url, data={"saved_query": str(ss.id)})

        # Assert
        self.assertTrue(r.context["from_saved_query"])
        self.assertEqual(r.context["saved_query"], ss)

    def test_knowledge_base_items_and_queues_in_context(self):
        # Arrange: staff user logs in
        self.client.force_login(self.staff_user)

        kbitems = KBItem.objects.all()
        kbitem_choices = [(item.pk, str(item)) for item in KBItem.objects.all()]
        queues = Queue.objects.all()

        # Act
        r = self.client.get(self.url)

        # Assert
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertQuerySetEqual(r.context["queue_choices"], queues)
        self.assertQuerySetEqual(r.context["kb_items"], kbitems)
        self.assertEqual(r.context["kbitem_choices"], kbitem_choices)

    def test_knowledge_base_items_not_in_context_if_setting_is_disabled(self):
        # Arrange
        KB_SETTINGS_PATH = "helpdesk.views.staff.helpdesk_settings.HELPDESK_KB_ENABLED"
        self.client.force_login(self.staff_user)

        # Act & Assert
        with patch(KB_SETTINGS_PATH, new=False):
            r = self.client.get(self.url)
            self.assertEqual(r.context["kb_items"], [])
            self.assertEqual(r.context["kbitem_choices"], [])

    def test_sorting_dropdown_hides_kbitem_when_kb_disabled(self):
        KB_SETTINGS_PATH = "helpdesk.views.staff.helpdesk_settings.HELPDESK_KB_ENABLED"
        self.client.force_login(self.staff_user)

        with patch(KB_SETTINGS_PATH, new=False):
            r = self.client.get(self.url)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertNotContains(r, "value='kbitem'")
