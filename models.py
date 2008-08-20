"""
Jutda Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from datetime import datetime

from django.contrib.auth.models import User
from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _


class Queue(models.Model):
    """
    A queue is a collection of tickets into what would generally be business
    areas or departments.

    For example, a company may have a queue for each Product they provide, or
    a queue for each of Accounts, Pre-Sales, and Support.

    """

    title = models.CharField(
        _('Title'),
        max_length=100,
        )

    slug = models.SlugField(
        _('Slug'),
        help_text=_('This slug is used when building ticket ID\'s. Once set, '
            'try not to change it or e-mailing may get messy.'),
        )

    email_address = models.EmailField(
        _('E-Mail Address'),
        blank=True,
        null=True,
        help_text=_('All outgoing e-mails for this queue will use this e-mail '
            'address. If you use IMAP or POP3, this should be the e-mail '
            'address for that mailbox.'),
        )

    allow_public_submission = models.BooleanField(
        _('Allow Public Submission?'),
        blank=True,
        null=True,
        help_text=_('Should this queue be listed on the public submission '
            'form?'),
        )

    allow_email_submission = models.BooleanField(
        _('Allow E-Mail Submission?'),
        blank=True,
        null=True,
        help_text=_('Do you want to poll the e-mail box below for new '
            'tickets?'),
        )

    escalate_days = models.IntegerField(
        _('Escalation Days'),
        blank=True,
        null=True,
        help_text=_('For tickets which are not held, how often do you wish to '
            'increase their priority? Set to 0 for no escalation.'),
        )

    new_ticket_cc = models.EmailField(
        _('New Ticket CC Address'),
        blank=True,
        null=True,
        help_text=_('If an e-mail address is entered here, then it will '
            'receive notification of all new tickets created for this queue'),
        )

    updated_ticket_cc = models.EmailField(
        _('Updated Ticket CC Address'),
        blank=True,
        null=True,
        help_text=_('If an e-mail address is entered here, then it will '
            'receive notification of all activity (new tickets, closed '
            'tickets, updates, reassignments, etc) for this queue'),
        )

    email_box_type = models.CharField(
        _('E-Mail Box Type'),
        max_length=5,
        choices=(('pop3', _('POP 3')), ('imap', _('IMAP'))),
        blank=True,
        null=True,
        help_text=_('E-Mail server type for creating tickets automatically '
            'from a mailbox - both POP3 and IMAP are supported.'),
        )

    email_box_host = models.CharField(
        _('E-Mail Hostname'),
        max_length=200,
        blank=True,
        null=True,
        help_text=_('Your e-mail server address - either the domain name or '
            'IP address. May be "localhost".'),
        )

    email_box_port = models.IntegerField(
        _('E-Mail Port'),
        blank=True,
        null=True,
        help_text=_('Port number to use for accessing e-mail. Default for '
            'POP3 is "110", and for IMAP is "143". This may differ on some '
            'servers. Leave it blank to use the defaults.'),
        )

    email_box_ssl = models.BooleanField(
        _('Use SSL for E-Mail?'),
        blank=True,
        null=True,
        help_text=_('Whether to use SSL for IMAP or POP3 - the default ports '
            'when using SSL are 993 for IMAP and 995 for POP3.'),
        )
             
    email_box_user = models.CharField(
        _('E-Mail Username'),
        max_length=200,
        blank=True,
        null=True,
        help_text=_('Username for accessing this mailbox.'),
        )

    email_box_pass = models.CharField(
        _('E-Mail Password'),
        max_length=200,
        blank=True,
        null=True,
        help_text=_('Password for the above username'),
        )

    email_box_imap_folder = models.CharField(
        _('IMAP Folder'),
        max_length=100,
        blank=True,
        null=True,
        help_text=_('If using IMAP, what folder do you wish to fetch messages '
            'from? This allows you to use one IMAP account for multiple '
            'queues, by filtering messages on your IMAP server into separate '
            'folders. Default: INBOX.'),
        )

    email_box_interval = models.IntegerField(
        _('E-Mail Check Interval'),
        help_text=_('How often do you wish to check this mailbox? (in Minutes)'),
        blank=True,
        null=True,
        default='5',
        )

    email_box_last_check = models.DateTimeField(
        blank=True,
        null=True,
        editable=False,
        # This is updated by management/commands/get_mail.py.
        )

    def __unicode__(self):
        return u"%s" % self.title

    class Meta:
        ordering = ('title',)

    def _from_address(self):
        """
        Short property to provide a sender address in SMTP format,
        eg 'Name <email>'. We do this so we can put a simple error message
        in the sender name field, so hopefully the admin can see and fix it.
        """
        if not self.email_address:
            return u'NO QUEUE EMAIL ADDRESS DEFINED <%s>' % settings.DEFAULT_FROM_EMAIL
        else:
            return u'%s <%s>' % (self.title, self.email_address)
    from_address = property(_from_address)

    def save(self):
        if self.email_box_type == 'imap' and not self.email_box_imap_folder:
            self.email_box_imap_folder = 'INBOX'

        if not self.email_box_port:
            if self.email_box_type == 'imap' and self.email_box_ssl:
                self.email_box_port = 993
            elif self.email_box_type == 'imap' and not self.email_box_ssl:
                self.email_box_port = 143
            elif self.email_box_type == 'pop3' and self.email_box_ssl:
                self.email_box_port = 995
            elif self.email_box_type == 'pop3' and not self.email_box_ssl:
                self.email_box_port = 110
        super(Queue, self).save()


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

    OPEN_STATUS = 1
    REOPENED_STATUS = 2
    RESOLVED_STATUS = 3
    CLOSED_STATUS = 4

    STATUS_CHOICES = (
        (OPEN_STATUS, _('Open')),
        (REOPENED_STATUS, _('Reopened')),
        (RESOLVED_STATUS, _('Resolved')),
        (CLOSED_STATUS, _('Closed')),
    )

    PRIORITY_CHOICES = (
        (1, _('1. Critical')),
        (2, _('2. High')),
        (3, _('3. Normal')),
        (4, _('4. Low')),
        (5, _('5. Very Low')),
    )

    title = models.CharField(
        _('Title'),
        max_length=200,
        )

    queue = models.ForeignKey(Queue)

    created = models.DateTimeField(
        _('Created'),
        blank=True,
        help_text=_('Date this ticket was first created'),
        )

    modified = models.DateTimeField(
        _('Modified'),
        blank=True,
        help_text=_('Date this ticket was most recently changed.'),
        )

    submitter_email = models.EmailField(
        _('Submitter E-Mail'),
        blank=True,
        null=True,
        help_text=_('The submitter will receive an email for all public '
            'follow-ups left for this task.'),
        )

    assigned_to = models.ForeignKey(
        User,
        related_name='assigned_to',
        blank=True,
        null=True,
        )

    status = models.IntegerField(
        _('Status'),
        choices=STATUS_CHOICES,
        default=OPEN_STATUS,
        )

    on_hold = models.BooleanField(
        _('On Hold'),
        blank=True,
        null=True,
        help_text=_('If a ticket is on hold, it will not automatically be '
            'escalated.'),
        )

    description = models.TextField(
        _('Description'),
        blank=True,
        null=True,
        help_text=_('The content of the customers query.'),
        )

    resolution = models.TextField(
        _('Resolution'),
        blank=True,
        null=True,
        help_text=_('The resolution provided to the customer by our staff.'),
        )

    priority = models.IntegerField(
        _('Priority'),
        choices=PRIORITY_CHOICES,
        default=3,
        blank=3,
        help_text=_('1 = Highest Priority, 5 = Low Priority'),
        )

    last_escalation = models.DateTimeField(
        blank=True,
        null=True,
        editable=False,
        help_text=_('The date this ticket was last escalated - updated '
            'automatically by management/commands/escalate_tickets.py.'),
        )

    def _get_assigned_to(self):
        """ Custom property to allow us to easily print 'Unassigned' if a
        ticket has no owner, or the users name if it's assigned. If the user
        has a full name configured, we use that, otherwise their username. """
        if not self.assigned_to:
            return _('Unassigned')
        else:
            if self.assigned_to.get_full_name():
                return self.assigned_to.get_full_name()
            else:
                return self.assigned_to
    get_assigned_to = property(_get_assigned_to)

    def _get_ticket(self):
        """ A user-friendly ticket ID, which is a combination of ticket ID
        and queue slug. This is generally used in e-mail subjects. """

        return u"[%s]" % (self.ticket_for_url)
    ticket = property(_get_ticket)

    def _get_ticket_for_url(self):
        """ A URL-friendly ticket ID, used in links. """
        return u"%s-%s" % (self.queue.slug, self.id)
    ticket_for_url = property(_get_ticket_for_url)

    def _get_priority_img(self):
        """ Image-based representation of the priority """
        from django.conf import settings
        return u"%s/helpdesk/priorities/priority%s.png" % (settings.MEDIA_URL, self.priority)
    get_priority_img = property(_get_priority_img)

    def _get_priority_span(self):
        """
        A HTML <span> providing a CSS_styled representation of the priority.
        """
        from django.utils.safestring import mark_safe
        return mark_safe(u"<span class='priority%s'>%s</span>" % (self.priority, self.priority))
    get_priority_span = property(_get_priority_span)

    def _get_status(self):
        """
        Displays the ticket status, with an "On Hold" message if needed.
        """
        held_msg = ''
        if self.on_hold: held_msg = _(' - On Hold')
        return u'%s%s' % (self.get_status_display(), held_msg)
    get_status = property(_get_status)

    def _get_ticket_url(self):
        """
        Returns a publicly-viewable URL for this ticket, used when giving
        a URL to the submitter of a ticket.
        """
        from django.contrib.sites.models import Site
        from django.core.urlresolvers import reverse
        site = Site.objects.get_current()
        return u"http://%s%s?ticket=%s&email=%s" % (
            site.domain,
            reverse('helpdesk_public_view'),
            self.ticket_for_url,
            self.submitter_email
            )
    ticket_url = property(_get_ticket_url)

    def _get_staff_url(self):
        """
        Returns a staff-only URL for this ticket, used when giving a URL to
        a staff member (in emails etc)
        """
        from django.contrib.sites.models import Site
        from django.core.urlresolvers import reverse
        site = Site.objects.get_current()
        return u"http://%s%s" % (
            site.domain,
            reverse('helpdesk_view',
            args=[self.id])
            )
    staff_url = property(_get_staff_url)

    class Meta:
        get_latest_by = "created"

    def __unicode__(self):
        return u'%s' % self.title

    def get_absolute_url(self):
        return ('helpdesk_view', [str(self.id)])
    get_absolute_url = models.permalink(get_absolute_url)

    def save(self):
        if not self.id:
            # This is a new ticket as no ID yet exists.
            self.created = datetime.now()

        if not self.priority:
            self.priority = 3

        self.modified = datetime.now()

        super(Ticket, self).save()


class FollowUpManager(models.Manager):
    def private_followups(self):
        return self.filter(public=False)

    def public_followups(self):
        return self.filter(public=True)


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

    ticket = models.ForeignKey(Ticket)

    date = models.DateTimeField(
        _('Date'),
        )

    title = models.CharField(
        _('Title'),
        max_length=200,
        blank=True,
        null=True,
        )

    comment = models.TextField(
        _('Comment'),
        blank=True,
        null=True,
        )

    public = models.BooleanField(
        _('Public'),
        blank=True,
        null=True,
        help_text=_('Public tickets are viewable by the submitter and all '
            'staff, but non-public tickets can only be seen by staff.'),
        )

    user = models.ForeignKey(
        User,
        blank=True,
        null=True,
        )

    new_status = models.IntegerField(
        _('New Status'),
        choices=Ticket.STATUS_CHOICES,
        blank=True,
        null=True,
        help_text=_('If the status was changed, what was it changed to?'),
        )

    objects = FollowUpManager()

    class Meta:
        ordering = ['date']

    def __unicode__(self):
        return u'%s' % self.title

    def get_absolute_url(self):
        return u"%s#followup%s" % (self.ticket.get_absolute_url(), self.id)

    def save(self):
        t = self.ticket
        t.modified = datetime.now()
        self.date = datetime.now()
        t.save()
        super(FollowUp, self).save()


class TicketChange(models.Model):
    """
    For each FollowUp, any changes to the parent ticket (eg Title, Priority,
    etc) are tracked here for display purposes.
    """

    followup = models.ForeignKey(FollowUp)

    field = models.CharField(
        _('Field'),
        max_length=100,
        )

    old_value = models.TextField(
        _('Old Value'),
        blank=True,
        null=True,
        )

    new_value = models.TextField(
        _('New Value'),
        blank=True,
        null=True,
        )

    def __unicode__(self):
        str = u'%s ' % field
        if not new_value:
            str += _('removed')
        elif not old_value:
            str += _('set to %s' % new_value)
        else:
            str += _('changed from "%(old_value)s" to "%(new_value)s"' % {
                'old_value': old_value,
                'new_value': new_value
                })
        return str


class DynamicFileField(models.FileField):
    """
    Allows model instance to specify upload_to dynamically.

    Model class should have a method like:

        def get_upload_to(self, attname):
            return 'path/to/%d' % self.parent.id

    Based on: http://scottbarnham.com/blog/2007/07/31/uploading-images-to-a-dynamic-path-with-django/
    """

    def contribute_to_class(self, cls, name):
        """Hook up events so we can access the instance."""
        super(DynamicFileField, self).contribute_to_class(cls, name)
        models.signals.post_init.connect(self._post_init, sender=cls)

    def _post_init(self, instance=None, **kwargs):
        """Get dynamic upload_to value from the model instance."""
        if hasattr(instance, 'get_upload_to'):
            self.upload_to = instance.get_upload_to(self.attname)

    def db_type(self):
        """Required by Django for ORM."""
        return 'varchar(100)'


class Attachment(models.Model):
    """
    Represents a file attached to a follow-up. This could come from an e-mail
    attachment, or it could be uploaded via the web interface.
    """

    followup = models.ForeignKey(FollowUp)

    file = DynamicFileField(
        _('File'),
        upload_to='helpdesk/attachments',
        )

    filename = models.CharField(
        _('Filename'),
        max_length=100,
        )

    mime_type = models.CharField(
        _('MIME Type'),
        max_length=30,
        )

    size = models.IntegerField(
        _('Size'),
        help_text=_('Size of this file in bytes'),
        )

    def get_upload_to(self, field_attname):
        """ Get upload_to path specific to this item """
        return u'helpdesk/attachments/%s/%s' % (
            self.followup.ticket.ticket_for_url,
            self.followup.id
            )

    def __unicode__(self):
        return u'%s' % self.filename

    class Meta:
        ordering = ['filename',]


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

    queues = models.ManyToManyField(
        Queue,
        blank=True,
        null=True,
        help_text=_('Leave blank to allow this reply to be used for all '
            'queues, or select those queues you wish to limit this reply to.'),
        )

    name = models.CharField(
        _('Name'),
        max_length=100,
        help_text=_('Only used to assist users with selecting a reply - not '
            'shown to the user.'),
        )

    body = models.TextField(
        _('Body'),
        help_text=_('Context available: {{ ticket }} - ticket object (eg '
            '{{ ticket.title }}); {{ queue }} - The queue; and {{ user }} '
            '- the current user.'),
        )

    class Meta:
        ordering = ['name',]

    def __unicode__(self):
        return u'%s' % self.name


class EscalationExclusion(models.Model):
    """
    An 'EscalationExclusion' lets us define a date on which escalation should
    not happen, for example a weekend or public holiday.

    You may also have a queue that is only used on one day per week.

    To create these on a regular basis, check out the README file for an
    example cronjob that runs 'create_escalation_exclusions.py'.
    """

    queues = models.ManyToManyField(
        Queue,
        blank=True,
        null=True,
        help_text=_('Leave blank for this exclusion to be applied to all '
            'queues, or select those queues you wish to exclude with this '
            'entry.'),
        )

    name = models.CharField(
        _('Name'),
        max_length=100,
        )

    date = models.DateField(
        _('Date'),
        help_text=_('Date on which escalation should not happen'),
        )

    def __unicode__(self):
        return u'%s' % self.name


class EmailTemplate(models.Model):
    """
    Since these are more likely to be changed than other templates, we store
    them in the database.

    This means that an admin can change email templates without having to have
    access to the filesystem.
    """

    template_name = models.CharField(
        _('Template Name'),
        max_length=100,
        unique=True,
        )

    subject = models.CharField(
        _('Subject'),
        max_length=100,
        help_text=_('This will be prefixed with "[ticket.ticket] ticket.title"'
            '. We recommend something simple such as "(Updated") or "(Closed)"'
            ' - the same context is available as in plain_text, below.'),
        )

    heading = models.CharField(
        _('Heading'),
        max_length=100,
        help_text=_('In HTML e-mails, this will be the heading at the top of '
            'the email - the same context is available as in plain_text, '
            'below.'),
        )

    plain_text = models.TextField(
        _('Plain Text'),
        help_text=_('The context available to you includes {{ ticket }}, '
            '{{ queue }}, and depending on the time of the call: '
            '{{ resolution }} or {{ comment }}.'),
        )

    html = models.TextField(
        _('HTML'),
        help_text=_('The same context is available here as in plain_text, '
            'above.'),
        )

    def __unicode__(self):
        return u'%s' % self.template_name

    class Meta:
        ordering = ['template_name',]


class KBCategory(models.Model):
    """
    Lets help users help themselves: the Knowledge Base is a categorised
    listing of questions & answers.
    """

    title = models.CharField(
        _('Title'),
        max_length=100,
        )

    slug = models.SlugField(
        _('Slug'),
        )

    description = models.TextField(
        _('Description'),
        )

    def __unicode__(self):
        return u'%s' % self.title

    class Meta:
        ordering = ['title',]

    def get_absolute_url(self):
        return ('helpdesk_kb_category', [str(self.slug)])
    get_absolute_url = models.permalink(get_absolute_url)


class KBItem(models.Model):
    """
    An item within the knowledgebase. Very straightforward question/answer
    style system.
    """
    category = models.ForeignKey(KBCategory)

    title = models.CharField(
        _('Title'),
        max_length=100,
        )

    question = models.TextField(
        _('Question'),
        )

    answer = models.TextField(
        _('Answer'),
        )

    votes = models.IntegerField(
        _('Votes'),
        help_text=_('Total number of votes cast for this item'),
        )

    recommendations = models.IntegerField(
        _('Positive Votes'),
        help_text=_('Number of votes for this item which were POSITIVE.'),
        )

    last_updated = models.DateTimeField(
        _('Last Updated'),
        help_text=_('The date on which this question was most recently '
            'changed.'),
        )

    def save(self):
        self.last_updated = datetime.now()
        return super(KBItem, self).save()

    def _score(self):
        if self.votes > 0:
            return int(self.recommendations / self.votes)
        else:
            return _('Unrated')
    score = property(_score)

    def __unicode__(self):
        return u'%s' % self.title

    class Meta:
        ordering = ['title',]

    def get_absolute_url(self):
        return ('helpdesk_kb_item', [str(self.id)])
    get_absolute_url = models.permalink(get_absolute_url)

