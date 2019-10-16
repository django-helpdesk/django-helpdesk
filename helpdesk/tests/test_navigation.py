# -*- coding: utf-8 -*-
import sys
from importlib import reload
from django.urls import reverse
from django.test import TestCase

from helpdesk import settings as helpdesk_settings
from helpdesk.models import Queue
from helpdesk.tests.helpers import (get_staff_user, reload_urlconf, User, create_ticket, print_response)


class KBDisabledTestCase(TestCase):
    def setUp(self):
        self.HELPDESK_KB_ENABLED = helpdesk_settings.HELPDESK_KB_ENABLED
        if self.HELPDESK_KB_ENABLED:
            helpdesk_settings.HELPDESK_KB_ENABLED = False
            reload_urlconf()

    def tearDown(self):
        if self.HELPDESK_KB_ENABLED:
            helpdesk_settings.HELPDESK_KB_ENABLED = True
            reload_urlconf()

    def test_navigation(self):
        """Test proper rendering of navigation.html by accessing the dashboard"""
        from django.urls import NoReverseMatch

        self.client.login(username=get_staff_user().get_username(), password='password')
        self.assertRaises(NoReverseMatch, reverse, 'helpdesk:kb_index')
        try:
            response = self.client.get(reverse('helpdesk:dashboard'))
        except NoReverseMatch as e:
            if 'helpdesk:kb_index' in e.message:
                self.fail("Please verify any unchecked references to helpdesk_kb_index (start with navigation.html)")
            else:
                raise
        else:
            self.assertEqual(response.status_code, 200)


class StaffUserTestCaseMixin(object):
    HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = False

    def setUp(self):
        self.original_setting = helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE
        helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = self.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE
        self.reload_views()

    def tearDown(self):
        helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = self.original_setting
        self.reload_views()

    def reload_views(self):
        try:
            reload(sys.modules['helpdesk.decorators'])
            reload(sys.modules['helpdesk.views.staff'])
            reload_urlconf()
        except KeyError:
            pass

    def test_anonymous_user(self):
        """Access to the dashboard always requires a login"""
        response = self.client.get(reverse('helpdesk:dashboard'), follow=True)
        self.assertTemplateUsed(response, 'helpdesk/registration/login.html')


class NonStaffUsersAllowedTestCase(StaffUserTestCaseMixin, TestCase):
    HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = True

    def test_non_staff_allowed(self):
        """If HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE is True,
        authenticated, non-staff users should be able to access
        the dashboard.
        """
        from helpdesk.decorators import is_helpdesk_staff

        user = User.objects.create_user(username='henry.wensleydale', password='gouda', email='wensleydale@example.com')

        self.assertTrue(is_helpdesk_staff(user))

        self.client.login(username=user.username, password='gouda')
        response = self.client.get(reverse('helpdesk:dashboard'), follow=True)
        self.assertTemplateUsed(response, 'helpdesk/dashboard.html')


class StaffUsersOnlyTestCase(StaffUserTestCaseMixin, TestCase):
    # Use default values
    HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = False

    def setUp(self):
        super().setUp()
        self.non_staff_user = User.objects.create_user(username='henry.wensleydale', password='gouda', email='wensleydale@example.com')

    def test_staff_user_detection(self):
        """Staff and non-staff users are correctly identified"""
        from helpdesk.decorators import is_helpdesk_staff

        self.assertFalse(is_helpdesk_staff(self.non_staff_user))
        self.assertTrue(is_helpdesk_staff(get_staff_user()))

    def test_staff_can_access_dashboard(self):
        """When HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE is False,
        staff users should be able to access the dashboard.
        """
        from helpdesk.decorators import is_helpdesk_staff

        user = get_staff_user()
        self.client.login(username=user.username, password='password')
        response = self.client.get(reverse('helpdesk:dashboard'), follow=True)
        self.assertTemplateUsed(response, 'helpdesk/dashboard.html')

    def test_non_staff_cannot_access_dashboard(self):
        """When HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE is False,
        non-staff users should not be able to access the dashboard.
        """
        from helpdesk.decorators import is_helpdesk_staff

        user = self.non_staff_user
        self.client.login(username=user.username, password=user.password)
        response = self.client.get(reverse('helpdesk:dashboard'), follow=True)
        self.assertTemplateUsed(response, 'helpdesk/registration/login.html')

    def test_staff_rss(self):
        """If HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE is False,
        staff users should be able to access rss feeds.
        """
        user = get_staff_user()
        self.client.login(username=user.username, password='password')
        response = self.client.get(reverse('helpdesk:rss_unassigned'), follow=True)
        self.assertContains(response, 'Unassigned Open and Reopened tickets')

    def test_non_staff_cannot_rss(self):
        """If HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE is False,
        non-staff users should not be able to access rss feeds.
        """
        user = self.non_staff_user
        self.client.login(username=user.username, password='password')
        queue = Queue.objects.create(
            title="Foo",
            slug="test_queue",
        )
        rss_urls = [
            reverse('helpdesk:rss_user', args=[user.username]),
            reverse('helpdesk:rss_user_queue', args=[user.username, 'test_queue']),
            reverse('helpdesk:rss_queue', args=['test_queue']),
            reverse('helpdesk:rss_unassigned'),
            reverse('helpdesk:rss_activity'),
        ]
        for rss_url in rss_urls:
            response = self.client.get(rss_url, follow=True)
            self.assertTemplateUsed(response, 'helpdesk/registration/login.html')


class CustomStaffUserTestCase(StaffUserTestCaseMixin, TestCase):
    @staticmethod
    def custom_staff_filter(user):
        """Arbitrary user validation function"""
        return user.is_authenticated and user.is_active and user.username.lower().endswith('wensleydale')

    HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = custom_staff_filter

    def test_custom_staff_pass(self):
        """If HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE is callable,
        a custom access rule is applied.
        """
        from helpdesk.decorators import is_helpdesk_staff

        user = User.objects.create_user(username='henry.wensleydale', password='gouda', email='wensleydale@example.com')

        self.assertTrue(is_helpdesk_staff(user))

        self.client.login(username=user.username, password='gouda')
        response = self.client.get(reverse('helpdesk:dashboard'), follow=True)
        self.assertTemplateUsed(response, 'helpdesk/dashboard.html')

    def test_custom_staff_fail(self):
        from helpdesk.decorators import is_helpdesk_staff

        user = User.objects.create_user(username='terry.milton', password='frog', email='milton@example.com')

        self.assertFalse(is_helpdesk_staff(user))

        self.client.login(username=user.username, password='frog')
        response = self.client.get(reverse('helpdesk:dashboard'), follow=True)
        self.assertTemplateUsed(response, 'helpdesk/registration/login.html')


class HomePageAnonymousUserTestCase(TestCase):
    def setUp(self):
        self.redirect_to_login = helpdesk_settings.HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT

    def tearDown(self):
        helpdesk_settings.HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT = self.redirect_to_login

    def test_homepage(self):
        helpdesk_settings.HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT = True
        response = self.client.get(reverse('helpdesk:home'))
        self.assertTemplateUsed('helpdesk/public_homepage.html')

    def test_redirect_to_login(self):
        """Unauthenticated users are redirected to the login page if HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT is True"""
        helpdesk_settings.HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT = True
        response = self.client.get(reverse('helpdesk:home'))
        self.assertRedirects(response, reverse('helpdesk:login'))


class HomePageTestCase(TestCase):
    def setUp(self):
        self.original_setting = helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE
        helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = False
        try:
            reload(sys.modules['helpdesk.views.public'])
        except KeyError:
            pass

    def tearDown(self):
        helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = self.original_setting
        reload(sys.modules['helpdesk.views.public'])

    def assertUserRedirectedToView(self, user, view_name):
        self.client.login(username=user.username, password='password')
        response = self.client.get(reverse('helpdesk:home'))
        self.assertRedirects(response, reverse(view_name))
        self.client.logout()

    def test_redirect_to_dashboard(self):
        """Authenticated users are redirected to the dashboard"""
        user = get_staff_user()

        # login_view_ticketlist is False...
        user.usersettings_helpdesk.login_view_ticketlist = False
        user.usersettings_helpdesk.save()
        self.assertUserRedirectedToView(user, 'helpdesk:dashboard')

    def test_no_user_settings_redirect_to_dashboard(self):
        """Authenticated users are redirected to the dashboard if user settings are missing"""
        from helpdesk.models import UserSettings
        user = get_staff_user()

        UserSettings.objects.filter(user=user).delete()
        self.assertUserRedirectedToView(user, 'helpdesk:dashboard')

    def test_redirect_to_ticket_list(self):
        """Authenticated users are redirected to the ticket list based on their user settings"""
        user = get_staff_user()
        user.usersettings_helpdesk.login_view_ticketlist = True
        user.usersettings_helpdesk.save()

        self.assertUserRedirectedToView(user, 'helpdesk:list')


class ReturnToTicketTestCase(TestCase):
    def test_staff_user(self):
        from helpdesk.views.staff import return_to_ticket

        user = get_staff_user()
        ticket = create_ticket()
        response = return_to_ticket(user, helpdesk_settings, ticket)
        self.assertEqual(response['location'], ticket.get_absolute_url())

    def test_non_staff_user(self):
        from helpdesk.views.staff import return_to_ticket

        user = User.objects.create_user(username='henry.wensleydale', password='gouda', email='wensleydale@example.com')
        ticket = create_ticket()
        response = return_to_ticket(user, helpdesk_settings, ticket)
        self.assertEqual(response['location'], ticket.ticket_url)
