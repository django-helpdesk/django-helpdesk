# -*- coding: utf-8 -*-
import sys
from django.contrib.auth import get_user_model

User = get_user_model()

from helpdesk.models import Ticket, Queue, UserSettings


def get_staff_user(username='helpdesk.staff', password='password'):
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = User.objects.create_user(username=username, password=password, email='staff@example.com')
        user.is_staff = True
        user.save()
    else:
        user.set_password(password)
        user.save()
    return user


def reload_urlconf(urlconf=None):

    from importlib import reload  # python 3 needs this import.

    if urlconf is None:
        from django.conf import settings

        urlconf = settings.ROOT_URLCONF

    if HELPDESK_URLCONF in sys.modules:
        reload(sys.modules[HELPDESK_URLCONF])

    if urlconf in sys.modules:
        reload(sys.modules[urlconf])

    from django.urls import clear_url_caches
    clear_url_caches()


def update_user_settings(user, **kwargs):
    usersettings = user.usersettings_helpdesk
    settings = usersettings.settings
    settings.update(kwargs)
    usersettings.settings = settings
    usersettings.save()


def delete_user_settings(user, *args):
    usersettings = user.usersettings_helpdesk
    settings = usersettings.settings
    for setting in args:
        if setting in settings:
            del settings[setting]
    usersettings.settings = settings
    usersettings.save()


def create_ticket(**kwargs):
    q = kwargs.get('queue', None)
    if q is None:
        try:
            q = Queue.objects.all()[0]
        except IndexError:
            q = Queue.objects.create(title='Test Q', slug='test', )
    data = {
        'title': "I wish to register a complaint",
        'queue': q,
    }
    data.update(kwargs)
    return Ticket.objects.create(**data)


HELPDESK_URLCONF = 'helpdesk.urls'
