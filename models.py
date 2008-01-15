"""                                     .. 
                                 .,::;::::::
                           ..,::::::::,,,,:::      Jutda Helpdesk - A Django
                      .,,::::::,,,,,,,,,,,,,::     powered ticket tracker for
                  .,::::::,,,,,,,,,,,,,,,,,,:;r.        small enterprise
                .::::,,,,,,,,,,,,,,,,,,,,,,:;;rr.
              .:::,,,,,,,,,,,,,,,,,,,,,,,:;;;;;rr      (c) Copyright 2008
            .:::,,,,,,,,,,,,,,,,,,,,,,,:;;;:::;;rr
          .:::,,,,,,,,,,,,,,,,,,,,.  ,;;;::::::;;rr           Jutda
        .:::,,,,,,,,,,,,,,,,,,.    .:;;:::::::::;;rr
      .:::,,,,,,,,,,,,,,,.       .;r;::::::::::::;r;   All Rights Reserved
    .:::,,,,,,,,,,,,,,,        .;r;;:::::::::::;;:.
  .:::,,,,,,,,,,,,,,,.       .;r;;::::::::::::;:.
 .;:,,,,,,,,,,,,,,,       .,;rr;::::::::::::;:.   This software is released 
.,:,,,,,,,,,,,,,.    .,:;rrr;;::::::::::::;;.  under a limited-use license that
  :,,,,,,,,,,,,,..:;rrrrr;;;::::::::::::;;.  allows you to freely download this
   :,,,,,,,:::;;;rr;;;;;;:::::::::::::;;,  software from it's manufacturer and
    ::::;;;;;;;;;;;:::::::::::::::::;;,  use it yourself, however you may not
    .r;;;;:::::::::::::::::::::::;;;,  distribute it. For further details, see
     .r;::::::::::::::::::::;;;;;:,  the enclosed LICENSE file.
      .;;::::::::::::::;;;;;:,.
       .;;:::::::;;;;;;:,.  Please direct people who wish to download this
        .r;;;;;;;;:,.  software themselves to www.jutda.com.au.
          ,,,..

$Id$

"""
from datetime import datetime

from django.contrib.auth.models import User
from django.db import models
from django.conf import settings

class Queue(models.Model):
    """
    A queue is a collection of tickets into what would generally be business 
    areas or departments.

    For example, a company may have a queue for each Product they provide, or 
    a queue for each of Accounts, Pre-Sales, and Support.

    TODO: Add e-mail inboxes (either using piped e-mail or IMAP/POP3) so we 
    can automatically get tickets via e-mail.
    """
    title = models.CharField(maxlength=100)
    slug = models.SlugField(help_text='This slug is used when building ticket ID\'s. Once set, try not to change it or e-mailing may get messy.')
    email_address = models.EmailField(blank=True, null=True, help_text='All outgoing e-mails for this queue will use this e-mail address. If you use IMAP or POP3, this shoul be the e-mail address for that mailbox.')

    def _from_address(self):
        if not self.email_address:
            return 'NO QUEUE EMAIL ADDRESS DEFINED <%s>' % settings.DEFAULT_FROM_EMAIL
        else:
            return '%s <%s>' % (self.title, self.email_address)
    from_address = property(_from_address)

    email_box_type = models.CharField(maxlength=5, choices=(('pop3', 'POP 3'),('imap', 'IMAP')), blank=True, null=True, help_text='E-Mail Server Type - Both POP3 and IMAP are supported. Select your email server type here.')
    email_box_host = models.CharField(maxlength=200, blank=True, null=True, help_text='Your e-mail server address - either the domain name or IP address. May be "localhost".')
    email_box_port = models.IntegerField(blank=True, null=True, help_text='Port number to use for accessing e-mail. Default for POP3 is "110", and for IMAP is "143". This may differ on some servers.')
    email_box_user = models.CharField(maxlength=200, blank=True, null=True, help_text='Username for accessing this mailbox.')
    email_box_pass = models.CharField(maxlength=200, blank=True, null=True, help_text='Password for the above username')
    email_box_imap_folder = models.CharField(maxlength=100, blank=True, null=True, help_text='If using IMAP, what folder do you wish to fetch messages from? This allows you to use one IMAP account for multiple queues, by filtering messages on your IMAP server into separate folders. Default: INBOX.')
    email_box_interval = models.IntegerField(help_text='How often do you wish to check this mailbox? (in Minutes)', blank=True, null=True, default='5')
    email_box_last_check = models.DateTimeField(blank=True, null=True, editable=False) # Updated by the auto-pop3-and-imap-checker

    def __unicode__(self):
        return u"%s" % self.title

    class Admin:
        list_display = ('title', 'slug', 'email_address')

    class Meta:
        ordering = ('title',)
        
    def save(self):
        if self.email_box_type == 'imap' and not self.email_box_imap_folder:
            self.email_box_imap_folder = 'INBOX'
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
        (OPEN_STATUS, 'Open'),
        (REOPENED_STATUS, 'Reopened'),
        (RESOLVED_STATUS, 'Resolved'),
        (CLOSED_STATUS, 'Closed'),
    )

    PRIORITY_CHOICES = (
        (1, '1 (Critical)'),
        (2, '2 (High)'),
        (3, '3 (Normal)'),
        (4, '4 (Low)'),
        (5, '5 (Very Low)'),
    )

    title = models.CharField(maxlength=200)
    queue = models.ForeignKey(Queue)
    created = models.DateTimeField(blank=True)
    modified = models.DateTimeField(blank=True)
    submitter_email = models.EmailField(blank=True, null=True, help_text='The submitter will receive an email for all public follow-ups left for this task.')
    assigned_to = models.ForeignKey(User, related_name='assigned_to', blank=True, null=True)
    status = models.IntegerField(choices=STATUS_CHOICES, default=OPEN_STATUS)

    description = models.TextField(blank=True, null=True)
    resolution = models.TextField(blank=True, null=True)

    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=3, blank=3)

    def _get_assigned_to(self):
        """ Custom property to allow us to easily print 'Unassigned' if a 
        ticket has no owner, or the users name if it's assigned. If the user 
        has a full name configured, we use that, otherwise their username. """
        if not self.assigned_to:
            return 'Unassigned'
        else:
            if self.assigned_to.get_full_name():
                return self.assigned_to.get_full_name()
            else:
                return self.assigned_to
    get_assigned_to = property(_get_assigned_to)

    def _get_ticket(self):
        """ A user-friendly ticket ID, which is a combination of ticket ID 
        and queue slug. This is generally used in e-mails. """

        return "[%s-%s]" % (self.queue.slug, self.id)
    ticket = property(_get_ticket)

    def _get_priority_img(self):
        from django.conf import settings
        return "%s/helpdesk/priorities/priority%s.png" % (settings.MEDIA_URL, self.priority)
    get_priority_img = property(_get_priority_img)

    class Admin:
        list_display = ('title', 'status', 'assigned_to', 'submitter_email',)
        date_hierarchy = 'created'
        list_filter = ('assigned_to', 'status', )
    
    class Meta:
        get_latest_by = "created"

    def __unicode__(self):
        return u'%s' % self.title

    def get_absolute_url(self):
        return ('helpdesk.views.view_ticket', [str(self.id)])
    get_absolute_url = models.permalink(get_absolute_url)

    def save(self):
        if not self.id:
            # This is a new ticket as no ID yet exists.
            self.created = datetime.now()
        
        if not self.priority:
            self.priority = 3
        
        self.modified = datetime.now()

        super(Ticket, self).save()


class FollowUp(models.Model):
    """ A FollowUp is a comment and/or change to a ticket. We keep a simple 
    title, the comment entered by the user, and the new status of a ticket 
    to enable easy flagging of details on the view-ticket page.

    The title is automatically generated at save-time, based on what action
    the user took.

    Tickets that aren't public are never shown to or e-mailed to the submitter, 
    although all staff can see them.
    """
    ticket = models.ForeignKey(Ticket)
    date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(maxlength=200, blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    public = models.BooleanField(blank=True, null=True)
    user = models.ForeignKey(User)
    
    new_status = models.IntegerField(choices=Ticket.STATUS_CHOICES, blank=True, null=True)

    class Meta:
        ordering = ['date']
    
    class Admin:
        pass

    def __unicode__(self):
        return u'%s' % self.title


    def save(self):
        t = self.ticket
        t.modified = datetime.now()
        t.save()
        super(FollowUp, self).save()

class TicketChange(models.Model):
    """ For each FollowUp, any changes to the parent ticket (eg Title, Priority,
    etc) are tracked here for display purposes.
    """
    followup = models.ForeignKey(FollowUp, edit_inline=models.TABULAR)
    field = models.CharField(maxlength=100, core=True)
    old_value = models.TextField(blank=True, null=True, core=True)
    new_value = models.TextField(blank=True, null=True, core=True)

    def __unicode__(self):
        str = u'%s ' % field
        if not new_value:
            str += 'removed'
        elif not old_value:
            str += 'set to %s' % new_value
        else:
            str += 'changed from "%s" to "%s"' % (old_value, new_value)
        return str

"""class Attachment(models.Model):
    followup = models.ForeignKey(FollowUp, edit_inline=models.TABULAR)
    file = models.FileField()
    filename = models.CharField(maxlength=100)
    mime_type = models.CharField(maxlength=30)
    size = models.IntegerField(help_text='Size of this file in bytes')

    def __unicode__(self):
        return u'%s' % self.filename

    class Meta:
        ordering = ['filename',] """

class PreSetReply(models.Model):
    """ We can allow the admin to define a number of pre-set replies, used to 
    simplify the sending of updates and resolutions. These are basically Django
    templates with a limited context - however if yo uwanted to get crafy it would
    be easy to write a reply that displays ALL updates in hierarchical order etc 
    with use of for loops over {{ ticket.followup_set.all }} and friends.
    
    When replying to a ticket, the user can select any reply set for the current
    queue, and the body text is fetched via AJAX."""
    
    queues = models.ManyToManyField(Queue, blank=True, null=True, help_text='Leave blank to allow this reply to be used for all queues, or select those queues you wish to limit this reply to.')
    name = models.CharField(max_length=100, help_text='Only used to assist users with selecting a reply - not shown to the user.')
    body = models.TextField(help_text='Context available: {{ ticket }} - ticket object (eg {{ ticket.title }}); {{ queue }} - The queue; and {{ user }} - the current user.')

    class Admin:
        list_display = ('name',)

    class Meta:
        ordering = ['name',]

    def __unicode__(self):
        return u'%s' % self.name
