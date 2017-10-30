from functools import wraps

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.utils.decorators import available_attrs
from django.contrib.auth.decorators import user_passes_test

from helpdesk import settings as helpdesk_settings

if callable(helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE):
    # apply a custom user validation condition
    is_helpdesk_staff = helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE
elif helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE:
    # treat 'normal' users like 'staff'
    is_helpdesk_staff = lambda u: u.is_authenticated() and u.is_active
else:
    is_helpdesk_staff = lambda u: u.is_authenticated() and u.is_active and u.is_staff

helpdesk_staff_member_required = user_passes_test(is_helpdesk_staff)
helpdesk_superuser_required = user_passes_test(lambda u: u.is_authenticated() and u.is_active and u.is_superuser)

def protect_view(view_func):
    """
    Decorator for protecting the views checking user, redirecting
    to the log-in page if necessary or returning 404 status code
    """
    @wraps(view_func, assigned=available_attrs(view_func))
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated() and helpdesk_settings.HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT:
            return HttpResponseRedirect(reverse('helpdesk:login'))
        elif not request.user.is_authenticated() and helpdesk_settings.HELPDESK_ANON_ACCESS_RAISES_404:
            raise Http404
        return view_func(request, *args, **kwargs)

    return _wrapped_view

