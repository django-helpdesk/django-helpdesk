# -*- coding: utf-8 -*-

"Management command to add create UserSettings"

from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from helpdesk.models import UserSettings
from helpdesk.settings import DEFAULT_USER_SETTINGS

class Command(BaseCommand):
    "create_usersettings command"

    help = _('Check for user without django-helpdesk UserSettings '
             'and create if missing')

    def handle(self, *args, **options):
        "handle command line"
        for u in User.objects.all():
            try:
                s = UserSettings.objects.get(user=u)
            except UserSettings.DoesNotExist:
                s = UserSettings(user=u, settings=DEFAULT_USER_SETTINGS)
                s.save()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4