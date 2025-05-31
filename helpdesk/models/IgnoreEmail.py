"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class IgnoreEmail(models.Model):
    """
    This model lets us easily ignore e-mails from certain senders when
    processing IMAP and POP3 mailboxes, eg mails from postmaster or from
    known trouble-makers.
    """

    class Meta:
        verbose_name = _("Ignored e-mail address")
        verbose_name_plural = _("Ignored e-mail addresses")

    queues = models.ManyToManyField(
        "helpdesk.Queue",
        blank=True,
        help_text=_(
            "Leave blank for this e-mail to be ignored on all queues, "
            "or select those queues you wish to ignore this e-mail for."
        ),
    )

    name = models.CharField(
        _("Name"),
        max_length=100,
    )

    date = models.DateField(
        _("Date"),
        help_text=_("Date on which this e-mail address was added"),
        blank=True,
        editable=False,
    )

    email_address = models.CharField(
        _("E-Mail Address"),
        max_length=150,
        help_text=_(
            "Enter a full e-mail address, or portions with "
            "wildcards, eg *@domain.com or postmaster@*."
        ),
    )

    keep_in_mailbox = models.BooleanField(
        _("Save Emails in Mailbox?"),
        blank=True,
        default=False,
        help_text=_(
            "Do you want to save emails from this address in the mailbox? "
            "If this is unticked, emails from this address will be deleted."
        ),
    )

    def __str__(self):
        return "%s" % self.name

    def save(self, *args, **kwargs):
        if not self.date:
            self.date = timezone.now()
        return super(IgnoreEmail, self).save(*args, **kwargs)

    def queue_list(self):
        """Return a list of the queues this IgnoreEmail applies to.
        If this IgnoreEmail applies to ALL queues, return '*'.
        """
        queues = self.queues.all().order_by("title")
        if len(queues) == 0:
            return "*"
        else:
            return ", ".join([str(q) for q in queues])

    def test(self, email):
        """
        Possible situations:
            1. Username & Domain both match
            2. Username is wildcard, domain matches
            3. Username matches, domain is wildcard
            4. username & domain are both wildcards
            5. Other (no match)

            1-4 return True, 5 returns False.
        """

        own_parts = self.email_address.split("@")
        email_parts = email.split("@")

        if (
            self.email_address == email
            or own_parts[0] == "*"
            and own_parts[1] == email_parts[1]
            or own_parts[1] == "*"
            and own_parts[0] == email_parts[0]
            or own_parts[0] == "*"
            and own_parts[1] == "*"
        ):
            return True
        else:
            return False
