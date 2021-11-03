"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/form_list.py - This template tag returns all organizations.
"""
from django import template
from seed.lib.superperms.orgs.models import (
    Organization,
    OrganizationUser,
)
register = template.Library()

@register.filter
def organization_info(user):
    '''
    Return the user with the following information:
        The list of orgs they have access to
        Their default organization ID
    '''
    if user.is_authenticated:
        return_info = {'orgs': user.orgs.all(),
                       'default_org_id': user.default_organization_id,
                       'default_org_name': Organization.objects.get(id=user.default_organization_id).name
                       }
    else:
        return_info = {}
    return return_info
