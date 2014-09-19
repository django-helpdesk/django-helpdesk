# -*- coding: utf-8 -*-
from django.contrib.auth.decorators import user_passes_test
from helpdesk import settings

if callable(settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE):
    # apply a custom user validation condition
    is_helpdesk_staff = settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE
elif settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE:
    # treat 'normal' users like 'staff'
    is_helpdesk_staff = lambda u: u.is_authenticated() and u.is_active
else:
    is_helpdesk_staff = lambda u: u.is_authenticated() and u.is_active and u.is_staff

helpdesk_staff_member_required = user_passes_test(is_helpdesk_staff)
helpdesk_superuser_required = user_passes_test(lambda u: u.is_authenticated() and u.is_active and u.is_superuser)
