"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from . import Queue


class PreSetReply(models.Model):
    """
    We can allow the admin to define a number of pre-set replies, used to
    simplify the sending of updates and resolutions. These are basically Django
    templates with a limited context - however if you wanted to get crafy it would
    be easy to write a reply that displays ALL updates in hierarchical order etc
    with use of for loops over {{ ticket.followup_set.all }} and friends.

    When replying to a ticket, the user can select any reply set for the current
    queue, and the body text is fetched via AJAX.
    """

    class Meta:
        ordering = ("name",)
        verbose_name = _("Pre-set reply")
        verbose_name_plural = _("Pre-set replies")

    queues = models.ManyToManyField(
        Queue,
        blank=True,
        help_text=_(
            "Leave blank to allow this reply to be used for all "
            "queues, or select those queues you wish to limit this reply to."
        ),
    )

    name = models.CharField(
        _("Name"),
        max_length=100,
        help_text=_(
            "Only used to assist users with selecting a reply - not shown to the user."
        ),
    )

    body = models.TextField(
        _("Body"),
        help_text=_(
            "Context available: {{ ticket }} - ticket object (eg "
            "{{ ticket.title }}); {{ queue }} - The queue; and {{ user }} "
            "- the current user."
        ),
    )

    def __str__(self):
        return "%s" % self.name
