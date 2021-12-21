# -*- coding: utf-8 -*-
import sys
from django.contrib.auth import get_user_model

from helpdesk.models import Ticket, Queue, UserSettings, FormType
from seed.lib.superperms.orgs.models import Organization, OrganizationUser, ROLE_BUILDING_VIEWER

User = get_user_model()


def get_user(username='helpdesk.staff',
             password='password',
             is_staff=False,
             is_superuser=False,
             organization=None):
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = User.objects.create_user(username=username,
                                        password=password,
                                        email='%s@example.com' % username,
                                        )
        if organization is not None:
            user.default_organization = organization
            organization.users.add(user)        # Gets added as a staff member automatically
            if not is_staff:
                OrganizationUser.objects.get(organization=organization, user=user).update(role_level=ROLE_BUILDING_VIEWER)

        user.is_superuser = is_superuser
        user.save()
    else:
        user.set_password(password)
        user.save()
    return user


# To be a staff member, the user must be connected to an organization. Alternatively, manually modify org permissions
# after creating the user
def get_staff_user(organization=None):
    return get_user(is_staff=True, organization=organization)


def reload_urlconf(urlconf=None):

    from importlib import reload

    if urlconf is None:
        from django.conf import settings

        urlconf = settings.ROOT_URLCONF

    if HELPDESK_URLCONF in sys.modules:
        reload(sys.modules[HELPDESK_URLCONF])

    if urlconf in sys.modules:
        reload(sys.modules[urlconf])

    from django.urls import clear_url_caches
    clear_url_caches()


def create_ticket(**kwargs):
    q = kwargs.get('queue', None)
    f = kwargs.get('ticket_form', None)
    try:
        org = Organization.objects.all()[0]
    except IndexError:
        org = Organization.objects.create()

    if q is None:
        try:
            q = Queue.objects.all()[0]
        except IndexError:
            q = Queue.objects.create(title='Test Q', slug='test', organization=org)
    if f is None:
        try:
            f = FormType.objects.all()[0]
        except IndexError:
            f = FormType.objects.create(organization=org)
    data = {
        'title': "I wish to register a complaint",
        'queue': q,
        'ticket_form': f
    }
    data.update(kwargs)
    return Ticket.objects.create(**data)


HELPDESK_URLCONF = 'helpdesk.urls'


def print_response(response, stdout=False):
    content = response.content.decode()
    if stdout:
        print(content)
    else:
        with open("response.html", "w") as f:  # pragma: no cover
            f.write(content)  # pragma: no cover
