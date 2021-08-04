#!/usr/bin/python
"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

See LICENSE for details.

create_usersettings.py - Easy way to create helpdesk-specific settings for
users who don't yet have them.
"""

from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from helpdesk.models import UserSettings

User = get_user_model()


class Command(BaseCommand):
    """create_usersettings command"""

    help = _('Check for user without django-helpdesk UserSettings '
             'and create settings if required. Uses '
             'settings.DEFAULT_USER_SETTINGS which can be overridden to '
             'suit your situation.')

    def handle(self, *args, **options):
        """handle command line"""
        for u in User.objects.all():
            UserSettings.objects.get_or_create(user=u)
