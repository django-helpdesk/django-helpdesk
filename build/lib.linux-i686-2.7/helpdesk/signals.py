

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _, ugettext
from django.contrib.auth.models import User
from .models import UserSettings
def create_usersettings(sender, created_models=[], instance=None, created=False, **kwargs):
    """
    Helper function to create UserSettings instances as
    required, eg when we first create the UserSettings database
    table via 'syncdb' or when we save a new user.

    If we end up with users with no UserSettings, then we get horrible
    'DoesNotExist: UserSettings matching query does not exist.' errors.
    """
    from helpdesk.settings import DEFAULT_USER_SETTINGS
    if sender == get_user_model() and created:
        # This is a new user, so lets create their settings entry.
        s, created = UserSettings.objects.get_or_create(user=instance, defaults={'settings': DEFAULT_USER_SETTINGS})
        s.save()
    elif UserSettings in created_models:
        User = get_user_model()
        # We just created the UserSettings model, lets create a UserSettings
        # entry for each existing user. This will only happen once (at install
        # time, or at upgrade) when the UserSettings model doesn't already
        # exist.
        for u in User.objects.all():
            try:
                s = UserSettings.objects.get(user=u)
            except UserSettings.DoesNotExist:
                s = UserSettings(user=u, settings=DEFAULT_USER_SETTINGS)
                s.save()

models.signals.post_migrate.connect(create_usersettings)
try:
    models.signals.post_save.connect(create_usersettings, sender=User)
except:
    signal_user = get_user_model()
    models.signals.post_save.connect(create_usersettings, sender=signal_user)
