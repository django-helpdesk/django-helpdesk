from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect

from django.contrib.auth.decorators import user_passes_test


from helpdesk import settings as helpdesk_settings
from seed.lib.superperms.orgs.decorators import requires_member, requires_building_user
from seed.lib.superperms.orgs.models import OrganizationUser


def check_staff_status(check_staff=False):  # 1st bool -- unused
    """
    Somewhat ridiculous currying to check user permissions without using lambdas.
    The function most only take one User parameter at the end for use with
    the Django function user_passes_test.
    """
    def check_superuser_status(check_superuser):  # 2nd bool
        def check_user_status(u):
            is_user = u.is_authenticated and u.is_active

            if not is_user:  # does not have an account in BEAM
                return False

            org_user = OrganizationUser.objects.filter(user=u)
            if not org_user.exists():
                return False
            org_user = org_user.first()  # TODO change later using the user's current org

            is_building_user = requires_building_user(org_user)
            is_member = requires_member(org_user)

            # If you're a building_user or lower than a member role in BEAM
            if is_building_user or not is_member:
                return False

            # Whether or not a user has is_staff set to true is irrelevant in Helpdesk.
            # Perms work this way:
            # Public = A building_owner/building_viewer or someone w/o an account => False
            # Staff = User w/ account, a member role, and isn't a building user => True for check_staff
            # Staff w/ privileges: User with is_superuser => True for check_superuser
            if check_superuser:
                return is_user and u.is_superuser
            else:
                return is_user and is_member

        return check_user_status
    return check_superuser_status


# Assigns global variable 'is_helpdesk_staff' to one of three possible results.
# For us, should just be one result -- we are removing the "allow non-staff ticket update" setting entirely.
is_helpdesk_staff = check_staff_status(True)(False)

helpdesk_staff_member_required = user_passes_test(check_staff_status(True)(False))
helpdesk_superuser_required = user_passes_test(check_staff_status(False)(True))


def protect_view(view_func):
    """
    Decorator for protecting the views checking user, redirecting
    to the log-in page if necessary or returning 404 status code
    """
    @wraps(view_func)
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
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated and not request.user.is_active:
            return redirect('helpdesk:login')
        if not helpdesk_staff_member_required(request.user):
            raise PermissionDenied()
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def superuser_required(view_func):
    """
    Decorator for superuser member the views checking user, redirecting
    to the log-in page if necessary or returning 403
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated and not request.user.is_active:
            return redirect('helpdesk:login')
        if not request.user.is_superuser:
            raise PermissionDenied()
        return view_func(request, *args, **kwargs)

    return _wrapped_view
