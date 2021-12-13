"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/saved_queries.py - This template tag returns previously saved
                                queries. Therefore you don't need to modify
                                any views.
"""
from django import template
from django.db.models import Q

from helpdesk.models import SavedSearch


register = template.Library()


@register.filter
def saved_queries(user):
    try:
        if user.is_anonymous:
            filters = Q(shared__exact=True)
        else:
            filters = (Q(shared__exact=True) & ~Q(opted_out_users__in=[user]))
        if user.is_authenticated:
            filters |= Q(user=user)
        user_saved_queries = SavedSearch.objects.filter(filters)
        return user_saved_queries
    except Exception as e:
        import sys
        print("'saved_queries' template tag (django-helpdesk) crashed with following error:",
              file=sys.stderr)
        print(e, file=sys.stderr)
        return ''
