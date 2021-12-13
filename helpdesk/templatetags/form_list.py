"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/form_list.py - This template tag returns all forms the user can access based on their org.
"""
from django import template
from helpdesk.models import FormType
from helpdesk.decorators import is_helpdesk_staff
from seed.lib.superperms.orgs.models import Organization

register = template.Library()


@register.simple_tag
def form_list(user, request):
    try:
        sidebar_form_list = []
        if user.is_authenticated and is_helpdesk_staff(user):
            sidebar_form_list = FormType.objects.filter(
                staff=True,
                organization=user.default_organization_id,
            ).values('name', 'id', 'organization__name')
        else:
            # Parse request for organization
            url_org = request.GET.get('org', '')
            if not url_org and not user.is_anonymous:  # Default to users default_organization if org in url unavailable
                org = Organization.objects.get(id=user.default_organization_id)
            else:
                org = Organization.objects.filter(name=url_org).first()
            sidebar_form_list = FormType.objects.filter(
                public=True,
                organization=org,
            ).values('name', 'id', 'organization__name')
        # else:
        #     # Non-logged in user should filter based on url
        #     sidebar_form_list = FormType.objects.filter(public=True).values('name', 'id', 'organization__name')
        return sidebar_form_list
    except Exception as e:
        import sys
        print("'form_list' template tag (django-helpdesk) crashed with following error:",
              file=sys.stderr)
        print(e, file=sys.stderr)
        return ''
