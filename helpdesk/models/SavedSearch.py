"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

class SavedSearch(models.Model):
    """
    Allow a user to save a ticket search, eg their filtering and sorting
    options, and optionally share it with other users. This lets people
    easily create a set of commonly-used filters, such as:
        * My tickets waiting on me
        * My tickets waiting on submitter
        * My tickets in 'Priority Support' queue with priority of 1
        * All tickets containing the word 'billing'.
         etc...
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("User"),
    )

    title = models.CharField(
        _("Query Name"),
        max_length=100,
        help_text=_("User-provided name for this query"),
    )

    shared = models.BooleanField(
        _("Shared With Other Users?"),
        blank=True,
        default=False,
        help_text=_("Should other users see this query?"),
    )

    query = models.TextField(
        _("Search Query"),
        help_text=_("Pickled query object. Be wary changing this."),
    )

    def __str__(self):
        if self.shared:
            return "%s (*)" % self.title
        else:
            return "%s" % self.title

    class Meta:
        verbose_name = _("Saved search")
        verbose_name_plural = _("Saved searches")
