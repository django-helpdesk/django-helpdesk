"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from . import Ticket


class Checklist(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name=_("Ticket"),
        related_name="checklists",
    )
    name = models.CharField(verbose_name=_("Name"), max_length=100)

    class Meta:
        verbose_name = _("Checklist")
        verbose_name_plural = _("Checklists")

    def __str__(self):
        return self.name

    def create_tasks_from_template(self, template):
        for position, task in enumerate(template.task_list):
            self.tasks.create(description=task, position=position)
