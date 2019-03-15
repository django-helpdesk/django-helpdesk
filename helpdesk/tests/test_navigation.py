# -*- coding: utf-8 -*-
from django.urls import reverse
from django.test import TestCase

from helpdesk.models import KBCategory
from helpdesk.tests.helpers import get_staff_user, reload_urlconf


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

    def test_public_homepage_with_kb_category(self):
        KBCategory.objects.create(title="KB Cat 1",
                                  slug="kbcat1",
                                  description="Some category of KB info")
        response = self.client.get(reverse('helpdesk:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/public_homepage.html')
