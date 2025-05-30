"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from . import Queue


class EscalationExclusion(models.Model):
    """
    An 'EscalationExclusion' lets us define a date on which escalation should
    not happen, for example a weekend or public holiday.

    You may also have a queue that is only used on one day per week.

    To create these on a regular basis, check out the README file for an
    example cronjob that runs 'create_escalation_exclusions.py'.
    """

    queues = models.ManyToManyField(
        Queue,
        blank=True,
        help_text=_(
            "Leave blank for this exclusion to be applied to all queues, "
            "or select those queues you wish to exclude with this entry."
        ),
    )

    name = models.CharField(
        _("Name"),
        max_length=100,
    )

    date = models.DateField(
        _("Date"),
        help_text=_("Date on which escalation should not happen"),
    )

    def __str__(self):
        return "%s" % self.name

    class Meta:
        verbose_name = _("Escalation exclusion")
        verbose_name_plural = _("Escalation exclusions")
