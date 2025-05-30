"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


def is_a_list_without_empty_element(task_list):
    if not isinstance(task_list, list):
        raise ValidationError(f"{task_list} is not a list")
    for task in task_list:
        if not isinstance(task, str):
            raise ValidationError(f"{task} is not a string")
        if task.strip() == "":
            raise ValidationError("A task cannot be an empty string")


class ChecklistTemplate(models.Model):
    name = models.CharField(verbose_name=_("Name"), max_length=100)
    task_list = models.JSONField(
        verbose_name=_("Task List"), validators=[is_a_list_without_empty_element]
    )

    class Meta:
        verbose_name = _("Checklist Template")
        verbose_name_plural = _("Checklist Templates")

    def __str__(self):
        return self.name
