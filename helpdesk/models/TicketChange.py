"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.utils.translation import gettext, gettext_lazy as _
from django.db import models


class TicketChange(models.Model):
    """
    For each FollowUp, any changes to the parent ticket (eg Title, Priority,
    etc) are tracked here for display purposes.
    """

    followup = models.ForeignKey(
        "helpdesk.FollowUp",
        on_delete=models.CASCADE,
        verbose_name=_("Follow-up"),
    )

    field = models.CharField(
        _("Field"),
        max_length=100,
    )

    old_value = models.TextField(
        _("Old Value"),
        blank=True,
        null=True,
    )

    new_value = models.TextField(
        _("New Value"),
        blank=True,
        null=True,
    )

    def __str__(self):
        out = "%s " % self.field
        if not self.new_value:
            out += gettext("removed")
        elif not self.old_value:
            out += gettext("set to %s") % self.new_value
        else:
            out += gettext('changed from "%(old_value)s" to "%(new_value)s"') % {
                "old_value": self.old_value,
                "new_value": self.new_value,
            }
        return out

    class Meta:
        verbose_name = _("Ticket change")
        verbose_name_plural = _("Ticket changes")
