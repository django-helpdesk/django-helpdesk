"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from . import Ticket


class TicketDependency(models.Model):
    """
    The ticket identified by `ticket` cannot be resolved until the ticket in `depends_on` has been resolved.
    To help enforce this, a helper function `can_be_resolved` on each Ticket instance checks that
    these have all been resolved.
    """

    class Meta:
        unique_together = (("ticket", "depends_on"),)
        verbose_name = _("Ticket dependency")
        verbose_name_plural = _("Ticket dependencies")

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name=_("Ticket"),
        related_name="ticketdependency",
    )

    depends_on = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name=_("Depends On Ticket"),
        related_name="depends_on",
    )

    def __str__(self):
        return "%s / %s" % (self.ticket, self.depends_on)
