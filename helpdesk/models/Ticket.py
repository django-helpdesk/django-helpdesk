"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import datetime
from helpdesk import settings as helpdesk_settings


from ..templated_email import send_templated_mail
from ..lib import format_time_spent, convert_value
from . import (
    mk_secret,
    FollowUp,
    TicketDependency,
    get_markdown,
    TicketCustomFieldValue,
    CustomField,
)


class Ticket(models.Model):
    """
    To allow a ticket to be entered as quickly as possible, only the
    bare minimum fields are required. These basically allow us to
    sort and manage the ticket. The user can always go back and
    enter more information later.

    A good example of this is when a customer is on the phone, and
    you want to give them a ticket ID as quickly as possible. You can
    enter some basic info, save the ticket, give the customer the ID
    and get off the phone, then add in further detail at a later time
    (once the customer is not on the line).

    Note that assigned_to is optional - unassigned tickets are displayed on
    the dashboard to prompt users to take ownership of them.
    """

    OPEN_STATUS = helpdesk_settings.OPEN_STATUS
    REOPENED_STATUS = helpdesk_settings.REOPENED_STATUS
    RESOLVED_STATUS = helpdesk_settings.RESOLVED_STATUS
    CLOSED_STATUS = helpdesk_settings.CLOSED_STATUS
    DUPLICATE_STATUS = helpdesk_settings.DUPLICATE_STATUS

    STATUS_CHOICES = helpdesk_settings.TICKET_STATUS_CHOICES
    OPEN_STATUSES = helpdesk_settings.TICKET_OPEN_STATUSES
    STATUS_CHOICES_FLOW = helpdesk_settings.TICKET_STATUS_CHOICES_FLOW

    PRIORITY_CHOICES = helpdesk_settings.TICKET_PRIORITY_CHOICES

    title = models.CharField(
        _("Title"),
        max_length=200,
    )

    queue = models.ForeignKey(
        "helpdesk.Queue",
        on_delete=models.CASCADE,
        verbose_name=_("Queue"),
    )

    created = models.DateTimeField(
        _("Created"),
        blank=True,
        help_text=_("Date this ticket was first created"),
    )

    modified = models.DateTimeField(
        _("Modified"),
        blank=True,
        help_text=_("Date this ticket was most recently changed."),
    )

    submitter_email = models.EmailField(
        _("Submitter E-Mail"),
        blank=True,
        null=True,
        help_text=_(
            "The submitter will receive an email for all public "
            "follow-ups left for this task."
        ),
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assigned_to",
        blank=True,
        null=True,
        verbose_name=_("Assigned to"),
    )

    status = models.IntegerField(
        _("Status"),
        choices=STATUS_CHOICES,
        default=OPEN_STATUS,
    )

    on_hold = models.BooleanField(
        _("On Hold"),
        blank=True,
        default=False,
        help_text=_("If a ticket is on hold, it will not automatically be escalated."),
    )

    description = models.TextField(
        _("Description"),
        blank=True,
        null=True,
        help_text=_("The content of the customers query."),
    )

    resolution = models.TextField(
        _("Resolution"),
        blank=True,
        null=True,
        help_text=_("The resolution provided to the customer by our staff."),
    )

    priority = models.IntegerField(
        _("Priority"),
        choices=PRIORITY_CHOICES,
        default=3,
        blank=3,
        help_text=_("1 = Highest Priority, 5 = Low Priority"),
    )

    due_date = models.DateTimeField(
        _("Due on"),
        blank=True,
        null=True,
    )

    last_escalation = models.DateTimeField(
        blank=True,
        null=True,
        editable=False,
        help_text=_(
            "The date this ticket was last escalated - updated "
            "automatically by management/commands/escalate_tickets.py."
        ),
    )

    secret_key = models.CharField(
        _("Secret key needed for viewing/editing ticket by non-logged in users"),
        max_length=36,
        default=mk_secret,
    )

    kbitem = models.ForeignKey(
        "KBItem",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        verbose_name=_(
            "Knowledge base item the user was viewing when they created this ticket."
        ),
    )

    merged_to = models.ForeignKey(
        "self",
        verbose_name=_("merged to"),
        related_name="merged_tickets",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    @property
    def time_spent(self):
        """Return back total time spent on the ticket. This is calculated value
        based on total sum from all FollowUps
        """
        res = FollowUp.objects.filter(ticket=self).aggregate(models.Sum("time_spent"))
        return res.get("time_spent__sum", datetime.timedelta(0))

    @property
    def time_spent_formated(self):
        return format_time_spent(self.time_spent)

    def send(self, roles, dont_send_to=None, **kwargs):
        """
        Send notifications to everyone interested in this ticket.

        The the roles argument is a dictionary mapping from roles to (template, context) pairs.
        If a role is not present in the dictionary, users of that type will not receive the notification.

        The following roles exist:

          - 'submitter'
          - 'new_ticket_cc'
          - 'ticket_cc'
          - 'assigned_to'

        Here is an example roles dictionary:

        {
            'submitter': (template_name, context),
            'assigned_to': (template_name2, context),
        }

        **kwargs are passed to send_templated_mail defined in templated_email.py

        returns the set of email addresses the notification was delivered to.

        """
        recipients = set()

        if dont_send_to is not None:
            recipients.update(dont_send_to)

        recipients.add(self.queue.email_address)

        def should_receive(email):
            return email and email not in recipients

        def send(role, recipient):
            if recipient and recipient not in recipients and role in roles:
                template, context = roles[role]
                send_templated_mail(
                    template,
                    context,
                    recipient,
                    sender=self.queue.from_address,
                    **kwargs,
                )
                recipients.add(recipient)

        send("submitter", self.submitter_email)
        send("ticket_cc", self.queue.updated_ticket_cc)
        send("new_ticket_cc", self.queue.new_ticket_cc)
        if self.assigned_to:
            send("assigned_to", self.assigned_to.email)
        if self.queue.enable_notifications_on_email_events:
            for cc in self.ticketcc_set.all():
                send("ticket_cc", cc.email_address)
        return recipients

    def _get_assigned_to(self):
        """Custom property to allow us to easily print 'Unassigned' if a
        ticket has no owner, or the users name if it's assigned. If the user
        has a full name configured, we use that, otherwise their username."""
        if not self.assigned_to:
            return _("Unassigned")
        else:
            if self.assigned_to.get_full_name():
                return self.assigned_to.get_full_name()
            else:
                return self.assigned_to.get_username()

    get_assigned_to = property(_get_assigned_to)

    def _get_ticket(self):
        """A user-friendly ticket ID, which is a combination of ticket ID
        and queue slug. This is generally used in e-mail subjects."""

        return "[%s]" % self.ticket_for_url

    ticket = property(_get_ticket)

    def _get_ticket_for_url(self):
        """A URL-friendly ticket ID, used in links."""
        return "%s-%s" % (self.queue.slug, self.id)

    ticket_for_url = property(_get_ticket_for_url)

    def _get_priority_css_class(self):
        """
        Return the boostrap class corresponding to the priority.
        """
        if self.priority == 2:
            return "warning"
        elif self.priority == 1:
            return "danger"
        elif self.priority == 5:
            return "success"
        else:
            return ""

    get_priority_css_class = property(_get_priority_css_class)

    def _get_status(self):
        """
        Displays the ticket status, with an "On Hold" message if needed.
        """
        held_msg = ""
        if self.on_hold:
            held_msg = _(" - On Hold")
        dep_msg = ""
        if not self.can_be_resolved:
            dep_msg = _(" - Open dependencies")
        return "%s%s%s" % (self.get_status_display(), held_msg, dep_msg)

    get_status = property(_get_status)

    def _get_allowed_status_flow(self):
        """
        Returns the list of allowed ticket status modifications for current state.
        """
        status_id_list = self.STATUS_CHOICES_FLOW.get(self.status, ())
        if status_id_list:
            # keep defined statuses in order and add labels for display
            status_dict = dict(helpdesk_settings.TICKET_STATUS_CHOICES)
            new_statuses = [
                (status_id, status_dict.get(status_id, _("No label")))
                for status_id in status_id_list
            ]
        else:
            # defaults to all choices if status was not mapped
            new_statuses = helpdesk_settings.TICKET_STATUS_CHOICES
        return new_statuses

    get_allowed_status_flow = property(_get_allowed_status_flow)

    def _get_ticket_url(self):
        """
        Returns a publicly-viewable URL for this ticket, used when giving
        a URL to the submitter of a ticket.
        """
        from django.contrib.sites.models import Site
        from django.core.exceptions import ImproperlyConfigured
        from django.urls import reverse

        try:
            site = Site.objects.get_current()
        except ImproperlyConfigured:
            site = Site(domain="configure-django-sites.com")
        if helpdesk_settings.HELPDESK_USE_HTTPS_IN_EMAIL_LINK:
            protocol = "https"
        else:
            protocol = "http"
        return "%s://%s%s?ticket=%s&email=%s&key=%s" % (
            protocol,
            site.domain,
            reverse("helpdesk:public_view"),
            self.ticket_for_url,
            self.submitter_email,
            self.secret_key,
        )

    ticket_url = property(_get_ticket_url)

    def _get_staff_url(self):
        """
        Returns a staff-only URL for this ticket, used when giving a URL to
        a staff member (in emails etc)
        """
        from django.contrib.sites.models import Site
        from django.core.exceptions import ImproperlyConfigured
        from django.urls import reverse

        try:
            site = Site.objects.get_current()
        except ImproperlyConfigured:
            site = Site(domain="configure-django-sites.com")
        if helpdesk_settings.HELPDESK_USE_HTTPS_IN_EMAIL_LINK:
            protocol = "https"
        else:
            protocol = "http"
        return "%s://%s%s" % (
            protocol,
            site.domain,
            reverse("helpdesk:view", args=[self.id]),
        )

    staff_url = property(_get_staff_url)

    def _can_be_resolved(self):
        """
        Returns a boolean.
        True = any dependencies are resolved
        False = There are non-resolved dependencies
        """
        return (
            TicketDependency.objects.filter(ticket=self)
            .filter(depends_on__status__in=Ticket.OPEN_STATUSES)
            .count()
            == 0
        )

    can_be_resolved = property(_can_be_resolved)

    def get_submitter_userprofile(self):
        User = get_user_model()
        try:
            return User.objects.get(email=self.submitter_email)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None

    class Meta:
        get_latest_by = "created"
        ordering = ("id",)
        verbose_name = _("Ticket")
        verbose_name_plural = _("Tickets")

    def __str__(self):
        return "%s %s" % (self.id, self.title)

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("helpdesk:view", args=(self.id,))

    def save(self, *args, **kwargs):
        if not self.id:
            # This is a new ticket as no ID yet exists.
            self.created = timezone.now()

        if not self.priority:
            self.priority = 3

        self.modified = timezone.now()

        if len(self.title) > 200:
            self.title = self.title[:197] + "..."

        super(Ticket, self).save(*args, **kwargs)

    @staticmethod
    def queue_and_id_from_query(query):
        # Apply the opposite logic here compared to self._get_ticket_for_url
        # Ensure that queues with '-' in them will work
        parts = query.split("-")
        queue = "-".join(parts[0:-1])
        return queue, parts[-1]

    def get_markdown(self):
        return get_markdown(self.description)

    @property
    def get_resolution_markdown(self):
        return get_markdown(self.resolution)

    def add_email_to_ticketcc_if_not_in(self, email=None, user=None, ticketcc=None):
        """
        Check that given email/user_email/ticketcc_email is not already present on the ticket
        (submitter email, assigned to, or in ticket CCs) and add it to a new ticket CC,
        or move the given one

        :param str email:
        :param User user:
        :param TicketCC ticketcc:
        :rtype: TicketCC|None
        """
        if ticketcc:
            email = ticketcc.display
        elif user:
            if user.email:
                email = user.email
            else:
                # Ignore if user has no email address
                return
        elif not email:
            raise ValueError(
                "You must provide at least one parameter to get the email from"
            )

        # Prepare all emails already into the ticket
        ticket_emails = [x.display for x in self.ticketcc_set.all()]
        if self.submitter_email:
            ticket_emails.append(self.submitter_email)
        if self.assigned_to and self.assigned_to.email:
            ticket_emails.append(self.assigned_to.email)

        # Check that email is not already part of the ticket
        if email not in ticket_emails:
            if ticketcc:
                ticketcc.ticket = self
                ticketcc.save(update_fields=["ticket"])
            elif user:
                ticketcc = self.ticketcc_set.create(user=user)
            else:
                ticketcc = self.ticketcc_set.create(email=email)
            return ticketcc

    def set_custom_field_values(self):
        for field in CustomField.objects.all():
            try:
                value = self.ticketcustomfieldvalue_set.get(field=field).value
            except TicketCustomFieldValue.DoesNotExist:
                value = None
            setattr(self, "custom_%s" % field.name, value)

    def save_custom_field_values(self, data):
        for field, value in data.items():
            if field.startswith("custom_"):
                field_name = field.replace("custom_", "", 1)
                customfield = CustomField.objects.get(name=field_name)
                cfv, created = self.ticketcustomfieldvalue_set.get_or_create(
                    field=customfield, defaults={"value": convert_value(value)}
                )
                if not created:
                    cfv.value = convert_value(value)
                    cfv.save()
