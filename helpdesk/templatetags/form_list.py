"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/form_list.py - This template tag returns all forms the user can access based on their helpdesk Org.
"""
from django import template
from helpdesk.models import FormType
from helpdesk.decorators import is_helpdesk_staff
from seed.lib.superperms.orgs.models import Organization, get_helpdesk_organizations, get_helpdesk_orgs_for_domain

register = template.Library()


@register.simple_tag
def form_list(user, request):
    """
    Given user and request,
    If user is staff, return the forms belonging to their Helpdesk Org
    If user is public or not logged in, return forms belonging to Org in Url. If no org in url, and user is logged
        in, return the forms belonging to their helpdesk Org. Otherwise, if one Helpdesk Org is available, return the
        forms belonging to that one Org.
    A non-logged in user, with no org in url with multiple Helpdesk Orgs will return no forms
    """
    try:
        if is_helpdesk_staff(user):
            sidebar_form_list = FormType.objects.filter(
                staff=True,
                organization=user.default_organization.helpdesk_organization_id,
            ).values('name', 'id', 'organization__name')
        else:
            domain_id = getattr(request, 'domain_id', 0)
            helpdesk_orgs = get_helpdesk_orgs_for_domain(domain_id)
            if len(helpdesk_orgs) == 1:
                org = helpdesk_orgs.first()
            else:
                # Parse request for organization
                url_org = request.GET.get('org', '')
                org = None
                if url_org:
                    org = Organization.objects.filter(name=url_org).first()
                    if org:
                        org = org.helpdesk_organization
                else:
                    if not user.is_anonymous:
                        org = user.default_organization.helpdesk_organization
                    elif user.is_anonymous and len(helpdesk_orgs) == 1:
                        org = helpdesk_orgs.first()
            sidebar_form_list = FormType.objects.filter(
                public=True,
                unlisted=False,
                organization=org,
            ).values('name', 'id', 'organization__name')
        return sidebar_form_list
    except Exception as e:
        import sys
        print("'form_list' template tag (django-helpdesk) crashed with following error:",
              file=sys.stderr)
        print(e, file=sys.stderr)
        return ''
