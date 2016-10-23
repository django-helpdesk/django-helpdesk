"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/saved_queries.py - This template tag returns previously saved
                                queries. Therefore you don't need to modify
                                any views.
"""

from django.template import Library
from django.db.models import Q
from helpdesk.models import SavedSearch


def saved_queries(user):
    try:
        user_saved_queries = SavedSearch.objects.filter(Q(user=user) | Q(shared__exact=True))
        return user_saved_queries
    except Exception as e:
        import sys
        print >> sys.stderr, "'saved_queries' template tag (django-helpdesk) crashed with following error:"
        print >> sys.stderr, e
        return ''

register = Library()
register.filter('saved_queries', saved_queries)
