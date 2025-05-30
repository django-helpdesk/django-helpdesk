"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
import re
import datetime

from ..lib import format_time_spent
from . import FollowUp

class Queue(models.Model):
    """
    A queue is a collection of tickets into what would generally be business
    areas or departments.

    For example, a company may have a queue for each Product they provide, or
    a queue for each of Accounts, Pre-Sales, and Support.

    """

    title = models.CharField(
        _("Title"),
        max_length=100,
    )

    slug = models.SlugField(
        _("Slug"),
        max_length=50,
        unique=True,
        help_text=_(
            "This slug is used when building ticket ID's. Once set, "
            "try not to change it or e-mailing may get messy."
        ),
    )

    email_address = models.EmailField(
        _("E-Mail Address"),
        blank=True,
        null=True,
        help_text=_(
            "All outgoing e-mails for this queue will use this e-mail "
            "address. If you use IMAP or POP3, this should be the e-mail "
            "address for that mailbox."
        ),
    )

    locale = models.CharField(
        _("Locale"),
        max_length=10,
        blank=True,
        null=True,
        help_text=_(
            "Locale of this queue. All correspondence in this "
            "queue will be in this language."
        ),
    )

    allow_public_submission = models.BooleanField(
        _("Allow Public Submission?"),
        blank=True,
        default=False,
        help_text=_("Should this queue be listed on the public submission form?"),
    )

    allow_email_submission = models.BooleanField(
        _("Allow E-Mail Submission?"),
        blank=True,
        default=False,
        help_text=_("Do you want to poll the e-mail box below for new tickets?"),
    )

    escalate_days = models.IntegerField(
        _("Escalation Days"),
        blank=True,
        null=True,
        help_text=_(
            "For tickets which are not held, how often do you wish to "
            "increase their priority? Set to 0 for no escalation."
        ),
    )

    new_ticket_cc = models.CharField(
        _("New Ticket CC Address"),
        blank=True,
        null=True,
        max_length=200,
        help_text=_(
            "If an e-mail address is entered here, then it will "
            "receive notification of all new tickets created for this queue. "
            "Enter a comma between multiple e-mail addresses."
        ),
    )

    updated_ticket_cc = models.CharField(
        _("Updated Ticket CC Address"),
        blank=True,
        null=True,
        max_length=200,
        help_text=_(
            "If an e-mail address is entered here, then it will "
            "receive notification of all activity (new tickets, closed "
            "tickets, updates, reassignments, etc) for this queue. Separate "
            "multiple addresses with a comma."
        ),
    )

    enable_notifications_on_email_events = models.BooleanField(
        _("Notify contacts when email updates arrive"),
        blank=True,
        default=False,
        help_text=_(
            "When an email arrives to either create a ticket or to "
            "interact with an existing discussion. Should email notifications be sent ? "
            "Note: the new_ticket_cc and updated_ticket_cc work independently of this feature"
        ),
    )

    email_box_type = models.CharField(
        _("E-Mail Box Type"),
        max_length=5,
        choices=(
            ("pop3", _("POP 3")),
            ("imap", _("IMAP")),
            ("oauth", _("IMAP OAUTH")),
            ("local", _("Local Directory")),
        ),
        blank=True,
        null=True,
        help_text=_(
            "E-Mail server type for creating tickets automatically "
            "from a mailbox - both POP3 and IMAP are supported, as well as "
            "reading from a local directory."
        ),
    )

    email_box_host = models.CharField(
        _("E-Mail Hostname"),
        max_length=200,
        blank=True,
        null=True,
        help_text=_(
            "Your e-mail server address - either the domain name or "
            'IP address. May be "localhost".'
        ),
    )

    email_box_port = models.IntegerField(
        _("E-Mail Port"),
        blank=True,
        null=True,
        help_text=_(
            "Port number to use for accessing e-mail. Default for "
            'POP3 is "110", and for IMAP is "143". This may differ on some '
            "servers. Leave it blank to use the defaults."
        ),
    )

    email_box_ssl = models.BooleanField(
        _("Use SSL for E-Mail?"),
        blank=True,
        default=False,
        help_text=_(
            "Whether to use SSL for IMAP or POP3 - the default ports "
            "when using SSL are 993 for IMAP and 995 for POP3."
        ),
    )

    email_box_user = models.CharField(
        _("E-Mail Username"),
        max_length=200,
        blank=True,
        null=True,
        help_text=_("Username for accessing this mailbox."),
    )

    email_box_pass = models.CharField(
        _("E-Mail Password"),
        max_length=200,
        blank=True,
        null=True,
        help_text=_("Password for the above username"),
    )

    email_box_imap_folder = models.CharField(
        _("IMAP Folder"),
        max_length=100,
        blank=True,
        null=True,
        help_text=_(
            "If using IMAP, what folder do you wish to fetch messages "
            "from? This allows you to use one IMAP account for multiple "
            "queues, by filtering messages on your IMAP server into separate "
            "folders. Default: INBOX."
        ),
    )

    email_box_local_dir = models.CharField(
        _("E-Mail Local Directory"),
        max_length=200,
        blank=True,
        null=True,
        help_text=_(
            "If using a local directory, what directory path do you "
            "wish to poll for new email? "
            "Example: /var/lib/mail/helpdesk/"
        ),
    )

    permission_name = models.CharField(
        _("Django auth permission name"),
        max_length=72,  # based on prepare_permission_name() pre-pending chars to slug
        blank=True,
        null=True,
        editable=False,
        help_text=_("Name used in the django.contrib.auth permission system"),
    )

    email_box_interval = models.IntegerField(
        _("E-Mail Check Interval"),
        help_text=_("How often do you wish to check this mailbox? (in Minutes)"),
        blank=True,
        null=True,
        default="5",
    )

    email_box_last_check = models.DateTimeField(
        blank=True,
        null=True,
        editable=False,
        # This is updated by management/commands/get_mail.py.
    )

    socks_proxy_type = models.CharField(
        _("Socks Proxy Type"),
        max_length=8,
        choices=(("socks4", _("SOCKS4")), ("socks5", _("SOCKS5"))),
        blank=True,
        null=True,
        help_text=_(
            "SOCKS4 or SOCKS5 allows you to proxy your connections through a SOCKS server."
        ),
    )

    socks_proxy_host = models.GenericIPAddressField(
        _("Socks Proxy Host"),
        blank=True,
        null=True,
        help_text=_("Socks proxy IP address. Default: 127.0.0.1"),
    )

    socks_proxy_port = models.IntegerField(
        _("Socks Proxy Port"),
        blank=True,
        null=True,
        help_text=_("Socks proxy port number. Default: 9150 (default TOR port)"),
    )

    logging_type = models.CharField(
        _("Logging Type"),
        max_length=5,
        choices=(
            ("none", _("None")),
            ("debug", _("Debug")),
            ("info", _("Information")),
            ("warn", _("Warning")),
            ("error", _("Error")),
            ("crit", _("Critical")),
        ),
        blank=True,
        null=True,
        help_text=_(
            "Set the default logging level. All messages at that "
            "level or above will be logged to the directory set "
            "below. If no level is set, logging will be disabled."
        ),
    )

    logging_dir = models.CharField(
        _("Logging Directory"),
        max_length=200,
        blank=True,
        null=True,
        help_text=_(
            "If logging is enabled, what directory should we use to "
            "store log files for this queue? "
            "The standard logging mechanims are used if no directory is set"
        ),
    )

    default_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="default_owner",
        blank=True,
        null=True,
        verbose_name=_("Default owner"),
    )

    dedicated_time = models.DurationField(
        help_text=_("Time to be spent on this Queue in total"), blank=True, null=True
    )

    def __str__(self):
        return "%s" % self.title

    class Meta:
        ordering = ("title",)
        verbose_name = _("Queue")
        verbose_name_plural = _("Queues")

    def _from_address(self):
        """
        Short property to provide a sender address in SMTP format,
        eg 'Name <email>'. We do this so we can put a simple error message
        in the sender name field, so hopefully the admin can see and fix it.
        """
        if not self.email_address:
            # must check if given in format "Foo <foo@example.com>"
            default_email = re.match(
                ".*<(?P<email>.*@*.)>", settings.DEFAULT_FROM_EMAIL
            )
            if default_email is not None:
                # already in the right format, so just include it here
                return "NO QUEUE EMAIL ADDRESS DEFINED %s" % settings.DEFAULT_FROM_EMAIL
            else:
                return (
                    "NO QUEUE EMAIL ADDRESS DEFINED <%s>" % settings.DEFAULT_FROM_EMAIL
                )
        else:
            return "%s <%s>" % (self.title, self.email_address)

    from_address = property(_from_address)

    @property
    def time_spent(self):
        """Return back total time spent on the ticket. This is calculated value
        based on total sum from all FollowUps
        """
        res = FollowUp.objects.filter(ticket__queue=self).aggregate(
            models.Sum("time_spent")
        )
        return res.get("time_spent__sum", datetime.timedelta(0))

    @property
    def time_spent_formated(self):
        return format_time_spent(self.time_spent)

    def prepare_permission_name(self):
        """Prepare internally the codename for the permission and store it in permission_name.
        :return: The codename that can be used to create a new Permission object.
        """
        # Prepare the permission associated to this Queue
        basename = "queue_access_%s" % self.slug
        self.permission_name = "helpdesk.%s" % basename
        return basename

    def save(self, *args, **kwargs):
        if self.email_box_type == "imap" and not self.email_box_imap_folder:
            self.email_box_imap_folder = "INBOX"

        if self.socks_proxy_type:
            if not self.socks_proxy_host:
                self.socks_proxy_host = "127.0.0.1"
            if not self.socks_proxy_port:
                self.socks_proxy_port = 9150
        else:
            self.socks_proxy_host = None
            self.socks_proxy_port = None

        if not self.email_box_port:
            if self.email_box_type == "imap" and self.email_box_ssl:
                self.email_box_port = 993
            elif self.email_box_type == "imap" and not self.email_box_ssl:
                self.email_box_port = 143
            elif self.email_box_type == "pop3" and self.email_box_ssl:
                self.email_box_port = 995
            elif self.email_box_type == "pop3" and not self.email_box_ssl:
                self.email_box_port = 110

        if not self.id:
            # Prepare the permission codename and the permission
            # (even if they are not needed with the current configuration)
            basename = self.prepare_permission_name()

            Permission.objects.create(
                name=_("Permission for queue: ") + self.title,
                content_type=ContentType.objects.get_for_model(self.__class__),
                codename=basename,
            )

        super(Queue, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        permission_name = self.permission_name
        super(Queue, self).delete(*args, **kwargs)

        # once the Queue is safely deleted, remove the permission (if exists)
        if permission_name:
            try:
                p = Permission.objects.get(codename=permission_name[9:])
                p.delete()
            except ObjectDoesNotExist:
                pass
