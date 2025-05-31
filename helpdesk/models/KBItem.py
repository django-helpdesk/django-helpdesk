"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from helpdesk import settings as helpdesk_settings
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .get_markdown import get_markdown
from .Ticket import Ticket


class KBItem(models.Model):
    """
    An item within the knowledgebase. Very straightforward question/answer
    style system.
    """

    voted_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="votes",
    )
    downvoted_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="downvotes",
    )
    category = models.ForeignKey(
        "helpdesk.KBCategory",
        on_delete=models.CASCADE,
        verbose_name=_("Category"),
    )

    title = models.CharField(
        _("Title"),
        max_length=100,
    )

    question = models.TextField(
        _("Question"),
    )

    answer = models.TextField(
        _("Answer"),
    )

    votes = models.IntegerField(
        _("Votes"),
        help_text=_("Total number of votes cast for this item"),
        default=0,
    )

    recommendations = models.IntegerField(
        _("Positive Votes"),
        help_text=_("Number of votes for this item which were POSITIVE."),
        default=0,
    )

    last_updated = models.DateTimeField(
        _("Last Updated"),
        help_text=_("The date on which this question was most recently changed."),
        blank=True,
    )

    team = models.ForeignKey(
        helpdesk_settings.HELPDESK_TEAMS_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("Team"),
        blank=True,
        null=True,
    )

    order = models.PositiveIntegerField(
        _("Order"),
        blank=True,
        null=True,
    )

    enabled = models.BooleanField(
        _("Enabled to display to users"),
        default=True,
    )

    def save(self, *args, **kwargs):
        if not self.last_updated:
            self.last_updated = timezone.now()
        return super(KBItem, self).save(*args, **kwargs)

    def get_team(self):
        return helpdesk_settings.HELPDESK_KBITEM_TEAM_GETTER(self)

    def _score(self):
        """Return a score out of 10 or Unrated if no votes"""
        if self.votes > 0:
            return (self.recommendations / self.votes) * 10
        else:
            return _("Unrated")

    score = property(_score)

    def __str__(self):
        return "%s: %s" % (self.category.title, self.title)

    class Meta:
        ordering = (
            "order",
            "title",
        )
        verbose_name = _("Knowledge base item")
        verbose_name_plural = _("Knowledge base items")

    def get_absolute_url(self):
        from django.urls import reverse

        return (
            str(reverse("helpdesk:kb_category", args=(self.category.slug,)))
            + "?kbitem="
            + str(self.pk)
        )

    def query_url(self):
        from django.urls import reverse

        return str(reverse("helpdesk:list")) + "?kbitem=" + str(self.pk)

    def num_open_tickets(self):
        return Ticket.objects.filter(kbitem=self, status__in=(1, 2)).count()

    def unassigned_tickets(self):
        return Ticket.objects.filter(
            kbitem=self, status__in=(1, 2), assigned_to__isnull=True
        )

    def get_markdown(self):
        return get_markdown(self.answer)
