"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from . import Checklist, ChecklistTaskQuerySet

class ChecklistTask(models.Model):
    checklist = models.ForeignKey(
        Checklist,
        on_delete=models.CASCADE,
        verbose_name=_("Checklist"),
        related_name="tasks",
    )
    description = models.CharField(verbose_name=_("Description"), max_length=250)
    completion_date = models.DateTimeField(
        verbose_name=_("Completion Date"), null=True, blank=True
    )
    position = models.PositiveSmallIntegerField(
        verbose_name=_("Position"), db_index=True
    )

    objects = ChecklistTaskQuerySet.as_manager()

    class Meta:
        verbose_name = _("Checklist Task")
        verbose_name_plural = _("Checklist Tasks")
        ordering = ("position",)

    def __str__(self):
        return self.description
