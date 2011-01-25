
"""
Default settings for jutda-helpdesk.

"""

from django.conf import settings

# check for django-tagging support
HAS_TAG_SUPPORT = 'tagging' in settings.INSTALLED_APPS
try:
        import tagging
except ImportError:
        HAS_TAG_SUPPORT = False
