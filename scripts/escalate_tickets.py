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
from datetime import datetime, timedelta
from django.db.models import Q
from helpdesk.models import Queue, Ticket, FollowUp
from helpdesk.lib import send_multipart_mail

def escalate_tickets():
    for q in Queue.objects.filter(escalate_hours__isnull=False).exclude(escalate_hours=0):
        
        if not q.last_escalation: q.last_escalation = datetime.now()-timedelta(hours=q.escalate_hours)

        if (q.last_escalation + timedelta(hours=q.escalate_hours) - timedelta(minutes=2)) > datetime.now():
            continue

        print "Processing: %s" % q
        
        q.last_escalation = datetime.now()
        q.save()

        for t in q.ticket_set.filter(Q(status=Ticket.OPEN_STATUS) | Q(status=Ticket.REOPENED_STATUS)).exclude(priority=1):
            t.priority -= 1
            t.save()

            f = FollowUp(
                ticket = t,
                title = 'Ticket Escalated',
                date=q.last_escalation,
                public=True,
                comment='Ticket escalated after %s hours' % q.escalate_hours,
            )
            f.save()

            tc = TicketChange(
                followup = f,
                field = 'priority',
                old_value = t.priority + 1,
                new_value = t.priority,
            )
            tc.save()

if __name__ == '__main__':
    escalate_tickets()
