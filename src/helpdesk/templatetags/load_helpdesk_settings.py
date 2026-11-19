"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/load_helpdesk_settings.py - returns the settings as defined in
                                    django-helpdesk/helpdesk/settings.py
"""

from django.template import Library

from helpdesk import settings as helpdesk_settings_config


def load_helpdesk_settings(request):
    return helpdesk_settings_config


register = Library()
register.filter("load_helpdesk_settings", load_helpdesk_settings)
