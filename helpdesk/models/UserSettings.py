"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .login_view_ticketlist_default import login_view_ticketlist_default
from .email_on_ticket_assign_default import email_on_ticket_assign_default
from .email_on_ticket_change_default import email_on_ticket_change_default
from .tickets_per_page_default import tickets_per_page_default
from .use_email_as_submitter_default import use_email_as_submitter_default



class UserSettings(models.Model):
    """
    A bunch of user-specific settings that we want to be able to define, such
    as notification preferences and other things that should probably be
    configurable.
    """

    PAGE_SIZES = ((10, "10"), (25, "25"), (50, "50"), (100, "100"))

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usersettings_helpdesk",
    )

    settings_pickled = models.TextField(
        _("DEPRECATED! Settings Dictionary DEPRECATED!"),
        help_text=_(
            "DEPRECATED! This is a base64-encoded representation of a pickled Python dictionary. "
            "Do not change this field via the admin."
        ),
        blank=True,
        null=True,
    )

    login_view_ticketlist = models.BooleanField(
        verbose_name=_("Show Ticket List on Login?"),
        help_text=_(
            "Display the ticket list upon login? Otherwise, the dashboard is shown."
        ),
        default=login_view_ticketlist_default,
    )

    email_on_ticket_change = models.BooleanField(
        verbose_name=_("E-mail me on ticket change?"),
        help_text=_(
            "If you're the ticket owner and the ticket is changed via the web by somebody else,"
            "do you want to receive an e-mail?"
        ),
        default=email_on_ticket_change_default,
    )

    email_on_ticket_assign = models.BooleanField(
        verbose_name=_("E-mail me when assigned a ticket?"),
        help_text=_(
            "If you are assigned a ticket via the web, do you want to receive an e-mail?"
        ),
        default=email_on_ticket_assign_default,
    )

    tickets_per_page = models.IntegerField(
        verbose_name=_("Number of tickets to show per page"),
        help_text=_("How many tickets do you want to see on the Ticket List page?"),
        default=tickets_per_page_default,
        choices=PAGE_SIZES,
    )

    use_email_as_submitter = models.BooleanField(
        verbose_name=_("Use my e-mail address when submitting tickets?"),
        help_text=_(
            "When you submit a ticket, do you want to automatically "
            "use your e-mail address as the submitter address? You "
            "can type a different e-mail address when entering the "
            "ticket if needed, this option only changes the default."
        ),
        default=use_email_as_submitter_default,
    )

    def __str__(self):
        return "Preferences for %s" % self.user

    class Meta:
        verbose_name = _("User Setting")
        verbose_name_plural = _("User Settings")
