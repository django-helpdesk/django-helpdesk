"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

The is_helpdesk_staff template filter returns True if the user qualifies as Helpdesk staff.
templatetags/helpdesk_staff.py
"""
import logging
from django.template import Library

from helpdesk.decorators import is_helpdesk_staff


logger = logging.getLogger(__name__)
register = Library()


@register.filter(name='is_helpdesk_staff')
def helpdesk_staff(user):
    try:
        return is_helpdesk_staff(user)
    except Exception:
        logger.exception(
            "'helpdesk_staff' template tag (django-helpdesk) crashed")
