# -*- coding: utf-8 -*-
from django.contrib.auth.decorators import user_passes_test
from helpdesk import settings as helpdesk_settings

if helpdesk_settings.HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK:
    # apply a custom user validation condition
    is_helpdesk_staff = helpdesk_settings.HELPDESK_CUSTOM_STAFF_FILTER_CALLBACK
elif helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE:
    # treat 'normal' users like 'staff'
    is_helpdesk_staff = lambda u: u.is_authenticated() and u.is_active
else:
    is_helpdesk_staff = lambda u: u.is_authenticated() and u.is_active and u.is_staff

helpdesk_staff_member_required = user_passes_test(is_helpdesk_staff)
helpdesk_superuser_required = user_passes_test(lambda u: u.is_authenticated() and u.is_active and u.is_superuser)
