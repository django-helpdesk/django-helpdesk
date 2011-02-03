"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/saved_queries.py - This template tag returns previously saved 
                                queries. Therefore you don't need to modify
                                any views.
"""

from django.template import Library
from django.db.models import Q
from helpdesk.models import SavedSearch


def saved_queries(request):
    user_saved_queries = SavedSearch.objects.filter(Q(user=request.user) | Q(shared__exact=True))
    return user_saved_queries

register = Library()
register.filter('saved_queries', saved_queries)
