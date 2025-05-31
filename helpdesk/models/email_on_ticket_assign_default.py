"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from .get_default_setting import get_default_setting


def email_on_ticket_assign_default():
    return get_default_setting("email_on_ticket_assign")
