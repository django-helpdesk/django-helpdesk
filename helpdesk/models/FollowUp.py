"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""
import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from helpdesk import settings as helpdesk_settings
from django.conf import settings


from ..lib import format_time_spent, daily_time_spent_calculation
from . import Ticket, FollowUpManager, Queue, get_markdown, TicketChange

class FollowUp(models.Model):
    """
    A FollowUp is a comment and/or change to a ticket. We keep a simple
    title, the comment entered by the user, and the new status of a ticket
    to enable easy flagging of details on the view-ticket page.

    The title is automatically generated at save-time, based on what action
    the user took.

    Tickets that aren't public are never shown to or e-mailed to the submitter,
    although all staff can see them.
    """

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name=_("Ticket"),
    )

    date = models.DateTimeField(_("Date"), default=timezone.now)

    title = models.CharField(
        _("Title"),
        max_length=200,
        blank=True,
        null=True,
    )

    comment = models.TextField(
        _("Comment"),
        blank=True,
        null=True,
    )

    public = models.BooleanField(
        _("Public"),
        blank=True,
        default=False,
        help_text=_(
            "Public tickets are viewable by the submitter and all "
            "staff, but non-public tickets can only be seen by staff."
        ),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("User"),
    )

    new_status = models.IntegerField(
        _("New Status"),
        choices=Ticket.STATUS_CHOICES,
        blank=True,
        null=True,
        help_text=_("If the status was changed, what was it changed to?"),
    )

    message_id = models.CharField(
        _("E-Mail ID"),
        max_length=256,
        blank=True,
        null=True,
        help_text=_("The Message ID of the submitter's email."),
        editable=False,
    )

    objects = FollowUpManager()

    time_spent = models.DurationField(
        help_text=_("Time spent on this follow up"), blank=True, null=True
    )

    class Meta:
        ordering = ("date",)
        verbose_name = _("Follow-up")
        verbose_name_plural = _("Follow-ups")

    def __str__(self):
        return "%s" % self.title

    def get_absolute_url(self):
        return "%s#followup%s" % (self.ticket.get_absolute_url(), self.id)

    def save(self, *args, **kwargs):
        self.ticket.modified = timezone.now()
        self.ticket.save()

        if helpdesk_settings.FOLLOWUP_TIME_SPENT_AUTO and not self.time_spent:
            self.time_spent = self.time_spent_calculation()

        super(FollowUp, self).save(*args, **kwargs)

    def get_markdown(self):
        return get_markdown(self.comment)

    @property
    def time_spent_formated(self):
        return format_time_spent(self.time_spent)

    def time_spent_calculation(self):
        "Returns timedelta according to rules settings."

        open_hours = helpdesk_settings.FOLLOWUP_TIME_SPENT_OPENING_HOURS
        holidays = helpdesk_settings.FOLLOWUP_TIME_SPENT_EXCLUDE_HOLIDAYS
        exclude_statuses = helpdesk_settings.FOLLOWUP_TIME_SPENT_EXCLUDE_STATUSES
        exclude_queues = helpdesk_settings.FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES

        # queryset for this ticket previous follow-ups
        prev_fup_qs = self.ticket.followup_set.all()
        if self.id:
            # if the follow-up exist in DB, only keep previous follow-ups
            prev_fup_qs = prev_fup_qs.filter(date__lt=self.date)

        # handle exclusions

        # extract previous status from follow-up or ticket for exclusion check
        if exclude_statuses:
            try:
                prev_fup = prev_fup_qs.latest("date")
                prev_status = prev_fup.new_status
            except ObjectDoesNotExist:
                prev_status = self.ticket.status

            # don't calculate status exclusions
            if prev_status in exclude_statuses:
                return datetime.timedelta(seconds=0)

        # find the previous queue for exclusion check
        if exclude_queues:
            try:
                prev_fup_ids = prev_fup_qs.values_list("id", flat=True)
                prev_queue_change = TicketChange.objects.filter(
                    followup_id__in=prev_fup_ids, field=_("Queue")
                ).latest("id")
                prev_queue = Queue.objects.get(pk=prev_queue_change.new_value)
                prev_queue_slug = prev_queue.slug
            except ObjectDoesNotExist:
                prev_queue_slug = self.ticket.queue.slug

            # don't calculate queue exclusions
            if prev_queue_slug in exclude_queues:
                return datetime.timedelta(seconds=0)

        # no exclusion found

        time_spent_seconds = 0

        # extract earliest from previous follow-up or ticket
        try:
            prev_fup = prev_fup_qs.latest("date")
            earliest = prev_fup.date
        except ObjectDoesNotExist:
            earliest = self.ticket.created

        # latest time is current follow-up date
        latest = self.date

        # split time interval by days
        days = latest.toordinal() - earliest.toordinal()
        for day in range(days + 1):
            if day == 0:
                start_day_time = earliest
                if days == 0:
                    # close single day case
                    end_day_time = latest
                else:
                    end_day_time = earliest.replace(
                        hour=23, minute=59, second=59, microsecond=999999
                    )
            elif day == days:
                start_day_time = latest.replace(hour=0, minute=0, second=0)
                end_day_time = latest
            else:
                middle_day_time = earliest + datetime.timedelta(days=day)
                start_day_time = middle_day_time.replace(hour=0, minute=0, second=0)
                end_day_time = middle_day_time.replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )

            if start_day_time.strftime("%Y-%m-%d") not in holidays:
                time_spent_seconds += daily_time_spent_calculation(
                    start_day_time, end_day_time, open_hours
                )

        return datetime.timedelta(seconds=time_spent_seconds)

