# -*- coding: utf-8 -*-
import sys
from django.core.urlresolvers import reverse
from django.test import TestCase

from helpdesk import settings
from helpdesk.tests.helpers import (get_staff_user, reload_urlconf, User, update_user_settings, delete_user_settings,
                                    create_ticket)


class KBDisabledTestCase(TestCase):
    def setUp(self):
        self.HELPDESK_KB_ENABLED = settings.HELPDESK_KB_ENABLED
        if self.HELPDESK_KB_ENABLED:
            settings.HELPDESK_KB_ENABLED = False
            reload_urlconf()

    def tearDown(self):
        if self.HELPDESK_KB_ENABLED:
            settings.HELPDESK_KB_ENABLED = True
            reload_urlconf()

    def test_navigation(self):
        """Test proper rendering of navigation.html by accessing the dashboard"""
        from django.core.urlresolvers import NoReverseMatch

        self.client.login(username=get_staff_user().username, password='password')
        self.assertRaises(NoReverseMatch, reverse, 'helpdesk_kb_index')
        try:
            response = self.client.get(reverse('helpdesk_dashboard'))
        except NoReverseMatch, e:
            if 'helpdesk_kb_index' in e.message:
                self.fail("Please verify any unchecked references to helpdesk_kb_index (start with navigation.html)")
            else:
                raise
        else:
            self.assertEqual(response.status_code, 200)


class StaffUserTestCaseMixin(object):
    HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = False
    HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK = None

    def setUp(self):
        self.old_settings = settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE, settings.HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK
        settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = self.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE
        settings.HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK = self.HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK
        self.reload_views()

    def tearDown(self):
        settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE, settings.HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK = self.old_settings
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
        response = self.client.get(reverse('helpdesk_dashboard'), follow=True)
        self.assertTemplateUsed(response, 'helpdesk/registration/login.html')


class NonStaffUsersAllowedTestCase(StaffUserTestCaseMixin, TestCase):
    HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = True
    HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK = None

    def test_non_staff_allowed(self):
        """If HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE is True,
        authenticated, non-staff users should be able to access
        the dashboard.
        """
        from helpdesk.decorators import is_helpdesk_staff

        user = User.objects.create_user(username='henry.wensleydale', password='gouda', email='wensleydale@example.com')

        self.assertTrue(is_helpdesk_staff(user))

        self.client.login(username=user.username, password='gouda')
        response = self.client.get(reverse('helpdesk_dashboard'), follow=True)
        self.assertTemplateUsed(response, 'helpdesk/dashboard.html')


class StaffUsersOnlyTestCase(StaffUserTestCaseMixin, TestCase):
    # Use default values
    HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = False
    HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK = None

    def test_non_staff(self):
        """Non-staff users are correctly identified"""
        from helpdesk.decorators import is_helpdesk_staff

        user = User.objects.create_user(username='henry.wensleydale', password='gouda', email='wensleydale@example.com')

        self.assertFalse(is_helpdesk_staff(user))

    def test_staff_only(self):
        """If HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE is False,
        only staff users should be able to access the dashboard.
        """
        from helpdesk.decorators import is_helpdesk_staff

        user = get_staff_user()

        self.assertTrue(is_helpdesk_staff(user))

        self.client.login(username=user.username, password='password')
        response = self.client.get(reverse('helpdesk_dashboard'), follow=True)
        self.assertTemplateUsed(response, 'helpdesk/dashboard.html')


class CustomStaffUserTestCase(StaffUserTestCaseMixin, TestCase):
    HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = False

    @staticmethod
    def HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK(user):
        """Arbitrary user validation function"""
        return user.is_authenticated() and user.is_active and user.username.lower().endswith('wensleydale')

    def test_custom_staff_pass(self):
        """If HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK is not None,
        a custom access rule is applied.
        """
        from helpdesk.decorators import is_helpdesk_staff

        user = User.objects.create_user(username='henry.wensleydale', password='gouda', email='wensleydale@example.com')

        self.assertTrue(is_helpdesk_staff(user))

        self.client.login(username=user.username, password='gouda')
        response = self.client.get(reverse('helpdesk_dashboard'), follow=True)
        self.assertTemplateUsed(response, 'helpdesk/dashboard.html')

    def test_custom_staff_fail(self):
        from helpdesk.decorators import is_helpdesk_staff

        user = User.objects.create_user(username='terry.milton', password='frog', email='milton@example.com')

        self.assertFalse(is_helpdesk_staff(user))

        self.client.login(username=user.username, password='frog')
        response = self.client.get(reverse('helpdesk_dashboard'), follow=True)
        self.assertTemplateUsed(response, 'helpdesk/registration/login.html')


class HomePageAnonymousUserTestCase(TestCase):
    def setUp(self):
        self.redirect_to_login = settings.HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT

    def tearDown(self):
        settings.HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT = self.redirect_to_login

    def test_homepage(self):
        settings.HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT = True
        response = self.client.get(reverse('helpdesk_home'))
        self.assertTemplateUsed('helpdesk/public_homepage.html')

    def test_redirect_to_login(self):
        """Unauthenticated users are redirected to the login page if HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT is True"""
        settings.HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT = True
        response = self.client.get(reverse('helpdesk_home'))
        self.assertRedirects(response, reverse('login'))


class HomePageTestCase(TestCase):
    def setUp(self):
        self.previous = settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE, settings.HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK
        settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = False
        settings.HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK = None
        try:
            reload(sys.modules['helpdesk.views.public'])
        except KeyError:
            pass

    def tearDown(self):
        settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE, settings.HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK = self.previous
        reload(sys.modules['helpdesk.views.public'])

    def assertUserRedirectedToView(self, user, view_name):
        self.client.login(username=user.username, password='password')
        response = self.client.get(reverse('helpdesk_home'))
        self.assertRedirects(response, reverse(view_name))
        self.client.logout()

    def test_redirect_to_dashboard(self):
        """Authenticated users are redirected to the dashboard"""
        user = get_staff_user()

        # login_view_ticketlist is False...
        update_user_settings(user, login_view_ticketlist=False)
        self.assertUserRedirectedToView(user, 'helpdesk_dashboard')

        # ... or missing
        delete_user_settings(user, 'login_view_ticketlist')
        self.assertUserRedirectedToView(user, 'helpdesk_dashboard')

    def test_no_user_settings_redirect_to_dashboard(self):
        """Authenticated users are redirected to the dashboard if user settings are missing"""
        from helpdesk.models import UserSettings
        user = get_staff_user()

        UserSettings.objects.filter(user=user).delete()
        self.assertUserRedirectedToView(user, 'helpdesk_dashboard')

    def test_redirect_to_ticket_list(self):
        """Authenticated users are redirected to the ticket list based on their user settings"""
        user = get_staff_user()
        update_user_settings(user, login_view_ticketlist=True)

        self.assertUserRedirectedToView(user, 'helpdesk_list')


class ReturnToTicketTestCase(TestCase):
    def test_staff_user(self):
        from helpdesk.views.staff import return_to_ticket

        user = get_staff_user()
        ticket = create_ticket()
        response = return_to_ticket(user, settings, ticket)
        self.assertEqual(response['location'], ticket.get_absolute_url())

    def test_non_staff_user(self):
        from helpdesk.views.staff import return_to_ticket

        user = User.objects.create_user(username='henry.wensleydale', password='gouda', email='wensleydale@example.com')
        ticket = create_ticket()
        response = return_to_ticket(user, settings, ticket)
        self.assertEqual(response['location'], ticket.ticket_url)
