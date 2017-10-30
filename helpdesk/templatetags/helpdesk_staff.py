"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/helpdesk_staff.py - The is_helpdesk_staff template filter returns True if the user qualifies as Helpdesk staff.
"""
import logging
from django.template import Library
from django.db.models import Q

from helpdesk.decorators import is_helpdesk_staff


logger = logging.getLogger(__name__)
register = Library()


@register.filter(name='is_helpdesk_staff')
def helpdesk_staff(user):
    try:
        return is_helpdesk_staff(user)
    except Exception, e:
        logger.exception("'helpdesk_staff' template tag (django-helpdesk) crashed")
