"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from . import Ticket, CustomField


class TicketCustomFieldValue(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name=_("Ticket"),
    )

    field = models.ForeignKey(
        CustomField,
        on_delete=models.CASCADE,
        verbose_name=_("Field"),
    )

    value = models.TextField(blank=True, null=True)

    def __str__(self):
        return "%s / %s" % (self.ticket, self.field)

    @property
    def default_value(self) -> str:
        return _("Not defined")

    class Meta:
        unique_together = (("ticket", "field"),)
        verbose_name = _("Ticket custom field value")
        verbose_name_plural = _("Ticket custom field values")
