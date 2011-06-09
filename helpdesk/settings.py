
"""
Default settings for django-helpdesk.

"""

from django.conf import settings

# check for django-tagging support
HAS_TAG_SUPPORT = 'tagging' in settings.INSTALLED_APPS
try:
        import tagging
except ImportError:
        HAS_TAG_SUPPORT = False

try:
    DEFAULT_USER_SETTINGS = settings.HELPDESK_DEFAULT_SETTINGS
except:
    DEFAULT_USER_SETTINGS = None

if type(DEFAULT_USER_SETTINGS) != type(dict()):
    DEFAULT_USER_SETTINGS = {
            'use_email_as_submitter': True,
            'email_on_ticket_assign': True,
            'email_on_ticket_change': True,
            'login_view_ticketlist': True,
            'email_on_ticket_apichange': True,
            'tickets_per_page': 25
            }

# show knowledgebase links?
HELPDESK_KB_ENABLED = getattr(settings, 'HELPDESK_KB_ENABLED', True)
