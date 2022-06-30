from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.db.models import Q
from django.contrib.auth import get_user_model

from django.contrib.auth.decorators import user_passes_test

from helpdesk import settings as helpdesk_settings
from seed.lib.superperms.orgs.decorators import requires_member, requires_building_user
from seed.lib.superperms.orgs.models import OrganizationUser, Organization, ROLE_MEMBER

User = get_user_model()


def check_staff_status(check_staff=False):  # 1st bool -- unused
    """
    Somewhat ridiculous currying to check user permissions without using lambdas.
    The function most only take one User parameter at the end for use with
    the Django function user_passes_test.

    is_helpdesk_staff params:
    - u: instance of User
    - org: instance of Organization (optional)

    If checking if the current user is staff in the same org as the request:    is_helpdesk_staff(user)
    If checking if a user is staff in a specific org:                           is_helpdesk_staff(user, org=org)

    Permissions are based on roles in BEAM, not on is_staff in table.
        Type        Description of type                                         => Result of is_helpdesk_staff
        ------      ------                                                      ----
        Public:     a building_owner/building_viewer or someone w/o an account  => False
        Staff:      user w/ account, a member role, isn't a building user       => True for check_staff
        Staff with privileges:  User with is_superuser                          => True for check_superuser


    """
    def check_superuser_status(check_superuser):  # 2nd bool
        def check_user_status(u, org=None):
            if not u:
                return False
            is_user = u.is_authenticated and u.is_active
            if not is_user:  # does not have an account in BEAM
                return False

            if org is None:  # check role in the user's current default_org
                helpdesk_org = u.default_organization.helpdesk_organization
            else:  # check role in the given org
                helpdesk_org = Organization.objects.get(id=org).helpdesk_organization

            try:
                org_user = OrganizationUser.objects.get(user=u, organization_id=helpdesk_org)
            except (OrganizationUser.MultipleObjectsReturned, OrganizationUser.DoesNotExist) as e:
                return False

            is_building_user = requires_building_user(org_user)
            is_member = requires_member(org_user)

            # If you're a building_user or lower than a member role in BEAM
            if is_building_user or not is_member:
                return False
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


def list_of_helpdesk_staff(organization, users=None):
    """
    Returns the list of Helpdesk staff users by organization.
    Staff users are either superusers in that organization, or have a role level above member.
    """
    if users is not None:
        staff_users = User.objects.filter(
            Q(id__in=users, organizationuser__organization=organization, is_active=True),
            Q(organizationuser__role_level__gte=ROLE_MEMBER) | Q(is_superuser=True)
        )
    else:
        staff_users = User.objects.filter(
            Q(organizationuser__organization=organization, is_active=True),
            Q(organizationuser__role_level__gte=ROLE_MEMBER) | Q(is_superuser=True)
        )
    return staff_users


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
