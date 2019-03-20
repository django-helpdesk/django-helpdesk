from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect

from django.utils.decorators import available_attrs


from helpdesk import settings as helpdesk_settings


def protect_view(view_func):
    """
    Decorator for protecting the views checking user, redirecting
    to the log-in page if necessary or returning 404 status code
    """
    @wraps(view_func, assigned=available_attrs(view_func))
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated and helpdesk_settings.HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT:
            return redirect('helpdesk:login')
        elif not request.user.is_authenticated and helpdesk_settings.HELPDESK_ANON_ACCESS_RAISES_404:
            raise Http404
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def staff_member_required(view_func):
    """
    Decorator for staff member the views checking user, redirecting
    to the log-in page if necessary or returning 403
    """
    @wraps(view_func, assigned=available_attrs(view_func))
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated and not request.user.is_active:
            return redirect('helpdesk:login')
        if not helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE and not request.user.is_staff:
            raise PermissionDenied()
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def superuser_required(view_func):
    """
    Decorator for superuser member the views checking user, redirecting
    to the log-in page if necessary or returning 403
    """
    @wraps(view_func, assigned=available_attrs(view_func))
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated and not request.user.is_active:
            return redirect('helpdesk:login')
        if not request.user.is_superuser:
            raise PermissionDenied()
        return view_func(request, *args, **kwargs)

    return _wrapped_view
