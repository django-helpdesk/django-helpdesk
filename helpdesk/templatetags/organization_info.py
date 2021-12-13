"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/organization_info.py - This template tag returns two pieces of information:
    a users default org -- based on the url if they are not staff or based on the users default_organization
                           field if they are staff.
    list of orgs        -- A queryset of the organizations the user is a part of if they are staff
"""
from django import template
from seed.lib.superperms.orgs.models import Organization, OrganizationUser
from urllib import parse
from helpdesk.decorators import is_helpdesk_staff

register = template.Library()


@register.simple_tag
def organization_info(user, url):
    """
    Given user and request,
    If user is staff, return Orgs to display in dropdown that they have access to in helpdesk
    If user is public, returns the one Org belonging to ticket
    """
    try:
        return_info = {}
        is_staff = is_helpdesk_staff(user)
        if is_staff:
            orgs = OrganizationUser.objects.filter(user=user, role_level__gt=3).values('organization')
            return_info['orgs'] = Organization.objects.filter(id__in=orgs)
            return_info['default_org'] = Organization.objects.get(id=user.default_organization_id)
        elif not is_staff:
            # Parse request
            query = parse.parse_qs(parse.urlsplit(url).query)  # Returns dict (key, list) of the url parameters
            url_org = query['org'][0] if 'org' in query.keys() else ""

            # Org in url has higher precedence than user's default org when they are not staff members
            if not url_org and not user.is_anonymous:  # Default to users default_organization if org in url unavailable
                return_info['default_org'] = Organization.objects.get(id=user.default_organization_id)
            else:
                return_info['default_org'] = Organization.objects.filter(name=url_org).first()
        return return_info
    except Exception as e:
        import sys
        print("'organization_info' template tag (django-helpdesk) crashed with following error:",
              file=sys.stderr)
        print(e, file=sys.stderr)
        return ''

@register.filter
def replace_slash(string):
    return string.replace("\\", "")
