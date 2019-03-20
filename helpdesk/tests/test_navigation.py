# -*- coding: utf-8 -*-
from django.urls import reverse
from django.test import TestCase

from helpdesk.models import KBCategory
from helpdesk.tests.helpers import get_user, reload_urlconf


class TestKBDisabled(TestCase):
    def setUp(self):
        from helpdesk import settings

        self.HELPDESK_KB_ENABLED = settings.HELPDESK_KB_ENABLED
        if self.HELPDESK_KB_ENABLED:
            settings.HELPDESK_KB_ENABLED = False
            reload_urlconf()

    def tearDown(self):
        from helpdesk import settings

        if self.HELPDESK_KB_ENABLED:
            settings.HELPDESK_KB_ENABLED = True
            reload_urlconf()

    def test_navigation(self):
        """Test proper rendering of navigation.html by accessing the dashboard"""
        from django.urls import NoReverseMatch

        self.client.login(username=get_user(is_staff=True).get_username(), password='password')
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

    def test_public_homepage_with_kb_category(self):
        KBCategory.objects.create(title="KB Cat 1",
                                  slug="kbcat1",
                                  description="Some category of KB info")
        response = self.client.get(reverse('helpdesk:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/public_homepage.html')


class TestDecorator(TestCase):

    def test_staff_member_restrictions(self):
        user = get_user(username='helpdesk.user',
                        password='password')

        self.client.login(username=user.get_username(),
                          password='password')
        response = self.client.get(reverse('helpdesk:list'))
        self.assertEqual(response.status_code, 403)

    def test_staff_member_access(self):
        user = get_user(username='helpdesk.user',
                        password='password',
                        is_staff=True)

        self.client.login(username=user.get_username(),
                          password='password')
        response = self.client.get(reverse('helpdesk:list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/ticket_list.html')

    def test_superuser_member_restrictions(self):
        user = get_user(username='helpdesk.superuser',
                        password='password',
                        is_staff=True)

        self.client.login(username=user.get_username(),
                          password='password')
        response = self.client.get(reverse('helpdesk:email_ignore'))
        self.assertEqual(response.status_code, 403)

    def test_superuser_member_access(self):
        user = get_user(username='helpdesk.superuser',
                        password='password',
                        is_staff=True,
                        is_superuser=True)

        self.client.login(username=user.get_username(),
                          password='password')
        response = self.client.get(reverse('helpdesk:email_ignore'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/email_ignore_list.html')
