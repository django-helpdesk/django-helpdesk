"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/load_helpdesk_settings.py - returns the settings as defined in 
                                    django-helpdesk/helpdesk/settings.py
"""

from django.template import Library
from helpdesk import settings as helpdesk_settings_config

def load_helpdesk_settings(request):
    try:
        return helpdesk_settings_config
    except Exception, e:
        import sys
        print >> sys.stderr,  "'load_helpdesk_settings' template tag (django-helpdesk) crashed with following error:"
        print >> sys.stderr,  e
        return ''

register = Library()
register.filter('load_helpdesk_settings', load_helpdesk_settings)
