"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/form_list.py - This template tag returns all forms.
"""
from django import template
from django.db.models import Q
from helpdesk.models import FormType
from helpdesk.decorators import is_helpdesk_staff

register = template.Library()

@register.filter
def form_list(user):
    try:
        sidebar_form_list = []
        if user.is_authenticated:
            sidebar_form_list = FormType.objects.filter(staff=True).values('name', 'id')  # TODO change to by-org or by-staff
        else:
            sidebar_form_list = FormType.objects.filter(public=True).values('name', 'id')  # TODO change to by-org or by-staff
        return sidebar_form_list
    except Exception as e:
        import sys
        print("'form_list' template tag (django-helpdesk) crashed with following error:",
              file=sys.stderr)
        print(e, file=sys.stderr)
        return ''
