"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class EmailTemplate(models.Model):
    """
    Since these are more likely to be changed than other templates, we store
    them in the database.

    This means that an admin can change email templates without having to have
    access to the filesystem.
    """

    template_name = models.CharField(
        _("Template Name"),
        max_length=100,
    )

    subject = models.CharField(
        _("Subject"),
        max_length=100,
        help_text=_(
            'This will be prefixed with "[ticket.ticket] ticket.title"'
            '. We recommend something simple such as "(Updated") or "(Closed)"'
            " - the same context is available as in plain_text, below."
        ),
    )

    heading = models.CharField(
        _("Heading"),
        max_length=100,
        help_text=_(
            "In HTML e-mails, this will be the heading at the top of "
            "the email - the same context is available as in plain_text, "
            "below."
        ),
    )

    plain_text = models.TextField(
        _("Plain Text"),
        help_text=_(
            "The context available to you includes {{ ticket }}, "
            "{{ queue }}, and depending on the time of the call: "
            "{{ resolution }} or {{ comment }}."
        ),
    )

    html = models.TextField(
        _("HTML"),
        help_text=_("The same context is available here as in plain_text, above."),
    )

    locale = models.CharField(
        _("Locale"),
        max_length=10,
        blank=True,
        null=True,
        help_text=_("Locale of this template."),
    )

    def __str__(self):
        return "%s" % self.template_name

    class Meta:
        ordering = ("template_name", "locale")
        verbose_name = _("e-mail template")
        verbose_name_plural = _("e-mail templates")
