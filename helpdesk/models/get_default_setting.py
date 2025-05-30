"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

def get_default_setting(setting):
    from helpdesk.settings import DEFAULT_USER_SETTINGS

    return DEFAULT_USER_SETTINGS[setting]
