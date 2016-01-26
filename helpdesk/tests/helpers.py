# -*- coding: utf-8 -*-
import sys
try:
    from django.contrib.auth import get_user_model
except ImportError:
    from django.contrib.auth.models import User
else:
    User = get_user_model()


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

    from imp import reload  # python 3 needs this import.

    if urlconf is None:
        from django.conf import settings

        urlconf = settings.ROOT_URLCONF

    if HELPDESK_URLCONF in sys.modules:
        reload(sys.modules[HELPDESK_URLCONF])

    if urlconf in sys.modules:
        reload(sys.modules[urlconf])

    from django.core.urlresolvers import clear_url_caches
    clear_url_caches()


HELPDESK_URLCONF = 'helpdesk.urls'
