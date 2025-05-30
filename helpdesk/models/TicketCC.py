"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from . import Ticket


class TicketCC(models.Model):
    """
    Often, there are people who wish to follow a ticket who aren't the
    person who originally submitted it. This model provides a way for those
    people to follow a ticket.

    In this circumstance, a 'person' could be either an e-mail address or
    an existing system user.
    """

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name=_("Ticket"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        help_text=_("User who wishes to receive updates for this ticket."),
        verbose_name=_("User"),
    )

    email = models.EmailField(
        _("E-Mail Address"),
        blank=True,
        null=True,
        help_text=_("For non-user followers, enter their e-mail address"),
    )

    can_view = models.BooleanField(
        _("Can View Ticket?"),
        blank=True,
        default=False,
        help_text=_("Can this CC login to view the ticket details?"),
    )

    can_update = models.BooleanField(
        _("Can Update Ticket?"),
        blank=True,
        default=False,
        help_text=_("Can this CC login and update the ticket?"),
    )

    def _email_address(self):
        if self.user and self.user.email is not None:
            return self.user.email
        else:
            return self.email

    email_address = property(_email_address)

    def _display(self):
        if self.user:
            return self.user
        else:
            return self.email

    display = property(_display)

    def __str__(self):
        return "%s for %s" % (self.display, self.ticket.title)

    def clean(self):
        if self.user and not self.user.email:
            raise ValidationError("User has no email address")
