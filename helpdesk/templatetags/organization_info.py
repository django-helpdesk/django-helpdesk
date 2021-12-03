"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/form_list.py - This template tag returns all organizations.
"""
from django import template
from seed.lib.superperms.orgs.models import Organization, OrganizationUser
from urllib import parse
from helpdesk.decorators import is_helpdesk_staff

register = template.Library()


@register.simple_tag
def organization_info(user, url):
    '''
    Given user and request,
    If user is staff, return Orgs to display in dropdown that they have access to in helpdesk
    If user is public, returns the one Org belonging to ticket
    '''
    return_info = {}
    is_staff = is_helpdesk_staff(user)
    if is_staff:
        orgs = OrganizationUser.objects.filter(user=user, role_level__gt=3).values('organization')
        return_info['orgs'] = Organization.objects.filter(id__in=orgs)
        return_info['default_org'] = Organization.objects.get(id=user.default_organization_id)
    elif not is_staff:
        # Parse request
        query = parse.parse_qs(parse.urlsplit(url).query)  # Returns dict (key, list) of the url parameters
        url_org = query['org'][0] if 'org' in query.keys() else -1

        return_info['orgs'] = Organization.objects.filter(id=url_org)

        # If they are logged in, their default org should still be the same,
        # but for a non-logged in user, change their default org
        if user.is_anonymous:
            return_info['default_org'] = return_info['orgs'].first()
        else:
            return_info['default_org'] = Organization.objects.get(id=user.default_organization_id)
    return return_info


@register.filter
def replace_slash(string):
    return string.replace("\\", "")
