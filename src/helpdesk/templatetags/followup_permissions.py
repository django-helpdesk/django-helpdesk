"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

Which actions a given user may take on a given follow-up. Kept here rather
than spelled out in the template so the menu and its entries agree on who
gets to see what.
templatetags/followup_permissions.py
"""

from django.template import Library
from helpdesk import settings as helpdesk_settings


register = Library()


@register.filter(name="can_edit_followup")
def can_edit_followup(followup, user):
    """Whether ``user`` may edit ``followup``.

    A follow-up with no author was not written by a staff member -- it was
    received by e-mail, submitted from the public form or raised by the
    helpdesk itself -- and editing those is not offered to anyone.
    """
    if not helpdesk_settings.HELPDESK_SHOW_EDIT_BUTTON_FOLLOW_UP:
        return False
    if not followup.user:
        return False
    return user == followup.user or user.is_superuser


@register.filter(name="can_delete_followup")
def can_delete_followup(followup, user):
    """Whether ``user`` may delete ``followup``."""
    return bool(
        helpdesk_settings.HELPDESK_SHOW_DELETE_BUTTON_SUPERUSER_FOLLOW_UP
        and user.is_superuser
    )
