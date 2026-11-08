"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

Which actions a given user may take on a given follow-up. Kept here rather
than spelled out in the template so the menu and its entries agree on who
gets to see what.
templatetags/followup_permissions.py
"""

from django.template import Library

from helpdesk import settings as helpdesk_settings
from helpdesk.user import HelpdeskUser

register = Library()


@register.filter(name="can_edit_followup")
def can_edit_followup(followup, user):
    """Whether ``user`` may edit ``followup``."""
    return HelpdeskUser(user).can_edit_followup(followup)


@register.filter(name="can_delete_followup")
def can_delete_followup(followup, user):
    """Whether ``user`` may delete ``followup``."""
    return bool(
        helpdesk_settings.HELPDESK_SHOW_DELETE_BUTTON_SUPERUSER_FOLLOW_UP
        and user.is_superuser
    )
