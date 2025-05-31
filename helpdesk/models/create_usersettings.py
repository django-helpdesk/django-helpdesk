"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.conf import settings
from django.db import models

from .UserSettings import UserSettings


def create_usersettings(sender, instance, created, **kwargs):
    """
    Helper function to create UserSettings instances as
    required, eg when we first create the UserSettings database
    table via 'syncdb' or when we save a new user.

    If we end up with users with no UserSettings, then we get horrible
    'DoesNotExist: UserSettings matching query does not exist.' errors.
    """
    if created:
        UserSettings.objects.create(user=instance)


models.signals.post_save.connect(create_usersettings, sender=settings.AUTH_USER_MODEL)
