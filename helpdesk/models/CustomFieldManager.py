"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models

class CustomFieldManager(models.Manager):
    def get_queryset(self):
        return super(CustomFieldManager, self).get_queryset().order_by("ordering")
