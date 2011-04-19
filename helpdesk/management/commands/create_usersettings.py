#!/usr/bin/python
"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

See LICENSE for details.

create_usersettings.py - Easy way to create helpdesk-specific settings for 
users who don't yet have them.
"""

from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from helpdesk.models import UserSettings
from helpdesk.settings import DEFAULT_USER_SETTINGS

class Command(BaseCommand):
    "create_usersettings command"

    help = _('Check for user without django-helpdesk UserSettings '
             'and create settings if required. Uses '
             'settings.DEFAULT_USER_SETTINGS which can be overridden to '
             'suit your situation.')

    def handle(self, *args, **options):
        "handle command line"
        for u in User.objects.all():
            try:
                s = UserSettings.objects.get(user=u)
            except UserSettings.DoesNotExist:
                s = UserSettings(user=u, settings=DEFAULT_USER_SETTINGS)
                s.save()
