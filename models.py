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
from django.db import models
from datetime import datetime
from django.contrib.auth.models import User
from django.db.models import permalink

class Queue(models.Model):
    title = models.CharField(maxlength=100)
    slug = models.SlugField()
    email_address = models.EmailField(blank=True, null=True)

    def __unicode__(self):
        return u"%s" % self.title

    class Admin:
        pass


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

    title = models.CharField(maxlength=200)
    queue = models.ForeignKey(Queue)
    created = models.DateTimeField(auto_now_add=True)
    submitter_email = models.EmailField(blank=True, null=True, help_text='The submitter will receive an email for all public follow-ups left for this task.')
    assigned_to = models.ForeignKey(User, related_name='assigned_to', blank=True, null=True)
    status = models.IntegerField(choices=STATUS_CHOICES, default=OPEN_STATUS)

    description = models.TextField(blank=True, null=True)
    resolution = models.TextField(blank=True, null=True)

    def _get_assigned_to(self):
        if not self.assigned_to:
            return 'Unassigned'
        else:
            if self.assigned_to.get_full_name():
                return self.assigned_to.get_full_name()
            else:
                return self.assigned_to
    get_assigned_to = property(_get_assigned_to)

    class Admin:
        list_display = ('title', 'status', 'assigned_to',)
        date_hierarchy = 'created'
        list_filter = ('assigned_to',)
        search_fields = ('title',)
    
    class Meta:
        get_latest_by = "created"

    def __unicode__(self):
        return '%s' % self.title

    def get_absolute_url(self):
        return ('helpdesk.views.view_ticket', [str(self.id)])
    get_absolute_url = permalink(get_absolute_url)

    def save(self):
        if not self.id:
            # This is a new ticket as no ID yet exists.
            self.created = datetime.now()

        super(Ticket, self).save()


class FollowUp(models.Model):
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
        return '%s' % self.title

class TicketChange(models.Model):
    followup = models.ForeignKey(FollowUp, edit_inline=models.TABULAR)
    field = models.CharField(maxlength=100, core=True)
    old_value = models.TextField(blank=True, null=True, core=True)
    new_value = models.TextField(blank=True, null=True, core=True)
