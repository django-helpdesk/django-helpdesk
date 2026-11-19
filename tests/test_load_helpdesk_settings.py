from django.test import SimpleTestCase

from helpdesk import settings as helpdesk_settings_config
from helpdesk.templatetags.load_helpdesk_settings import load_helpdesk_settings


class LoadHelpdeskSettingsTests(SimpleTestCase):
    def test_returns_helpdesk_settings(self):
        self.assertIs(load_helpdesk_settings(None), helpdesk_settings_config)
