"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class KBCategory(models.Model):
    """
    Lets help users help themselves: the Knowledge Base is a categorised
    listing of questions & answers.
    """

    name = models.CharField(
        _("Name of the category"),
        max_length=100,
    )

    title = models.CharField(
        _("Title on knowledgebase page"),
        max_length=100,
    )

    slug = models.SlugField(
        _("Slug"),
    )

    description = models.TextField(
        _("Description"),
    )

    queue = models.ForeignKey(
        "helpdesk.Queue",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        verbose_name=_(
            "Default queue when creating a ticket after viewing this category."
        ),
    )

    public = models.BooleanField(
        default=True, verbose_name=_("Is KBCategory publicly visible?")
    )

    def __str__(self):
        return "%s" % self.name

    class Meta:
        ordering = ("title",)
        verbose_name = _("Knowledge base category")
        verbose_name_plural = _("Knowledge base categories")

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("helpdesk:kb_category", kwargs={"slug": self.slug})
