from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.forms import UserSettingsForm
from helpdesk.models import FollowUp, Queue, Ticket, UserSettings

User = get_user_model()


class TicketRespondLayoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        self.queue = Queue.objects.create(title="Queue", slug="q")
        self.ticket = Ticket.objects.create(
            title="Printer on fire",
            submitter_email="submitter@example.com",
            queue=self.queue,
        )
        FollowUp.objects.create(
            ticket=self.ticket, title="First followup", comment="Hello"
        )
        self.url = reverse("helpdesk:view", kwargs={"ticket_id": self.ticket.id})
        self.client.force_login(self.user)

    def set_layout(self, layout):
        self.user.usersettings_helpdesk.ticket_respond_layout = layout
        self.user.usersettings_helpdesk.save()

    def get_page(self):
        return self.client.get(self.url).content.decode()

    def test_default_layout_is_tabs(self):
        self.assertEqual(
            self.user.usersettings_helpdesk.ticket_respond_layout,
            UserSettings.RESPOND_LAYOUT_TABS,
        )
        page = self.get_page()
        self.assertIn('id="respond-tab-pane"', page)
        self.assertIn('id="followup-tab-pane"', page)
        self.assertNotIn('id="respond-card"', page)

    def test_bottom_layout_places_respond_after_followups(self):
        self.set_layout(UserSettings.RESPOND_LAYOUT_BOTTOM)
        page = self.get_page()
        self.assertNotIn('id="ticketTab"', page)
        self.assertLess(
            page.index('id="followup-list"'), page.index('id="respond-card"')
        )

    def test_top_layout_places_respond_before_followups(self):
        self.set_layout(UserSettings.RESPOND_LAYOUT_TOP)
        page = self.get_page()
        self.assertNotIn('id="ticketTab"', page)
        self.assertLess(
            page.index('id="respond-card"'), page.index('id="followup-list"')
        )

    def test_respond_form_shown_without_followups(self):
        FollowUp.objects.all().delete()
        for layout in (
            UserSettings.RESPOND_LAYOUT_BOTTOM,
            UserSettings.RESPOND_LAYOUT_TOP,
        ):
            with self.subTest(layout=layout):
                self.set_layout(layout)
                page = self.get_page()
                self.assertIn('id="respond-card"', page)
                self.assertNotIn('id="followup-card"', page)

    def test_missing_user_settings_falls_back_to_tabs(self):
        UserSettings.objects.filter(user=self.user).delete()
        page = self.get_page()
        self.assertIn('id="respond-tab-pane"', page)

    def test_user_settings_form_saves_layout(self):
        settings = self.user.usersettings_helpdesk
        form = UserSettingsForm(
            {
                "login_view_ticketlist": True,
                "email_on_ticket_change": True,
                "email_on_ticket_assign": True,
                "tickets_per_page": 25,
                "use_email_as_submitter": True,
                "ticket_respond_layout": UserSettings.RESPOND_LAYOUT_TOP,
            },
            instance=settings,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        settings.refresh_from_db()
        self.assertEqual(
            settings.ticket_respond_layout, UserSettings.RESPOND_LAYOUT_TOP
        )
