#!/usr/bin/python
"""
Jutda Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

scripts/get_email.py - Designed to be run from cron, this script checks the
                       POP and IMAP boxes defined for the queues within a 
                       helpdesk, creating tickets from the new messages (or 
                       adding to existing tickets if needed)
"""
import poplib
import imaplib
from datetime import datetime, timedelta
import email, mimetypes, re
from email.Utils import parseaddr
from helpdesk.models import Queue, Ticket, FollowUp, Attachment
from helpdesk.lib import send_templated_mail

def process_email():
    for q in Queue.objects.filter(email_box_type__isnull=False, allow_email_submission=True):
        if not q.email_box_last_check: q.email_box_last_check = datetime.now()-timedelta(minutes=30)
        if not q.email_box_interval: q.email_box_interval = 0

        if (q.email_box_last_check + timedelta(minutes=q.email_box_interval)) > datetime.now():
            continue

        process_queue(q)

        q.email_box_last_check = datetime.now()
        q.save()

def process_queue(q):
    print "Processing: %s" % q
    if q.email_box_type == 'pop3':
        server = poplib.POP3(q.email_box_host)
        server.getwelcome()
        server.user(q.email_box_user)
        server.pass_(q.email_box_pass)

        messagesInfo = server.list()[1]

        for msg in messagesInfo:
            msgNum = msg.split(" ")[0]
            msgSize = msg.split(" ")[1]
            
            full_message = "\n".join(server.retr(msgNum)[1])
            ticket_from_message(message=full_message, queue=q)
            
            server.dele(msgNum)
        server.quit()

    elif q.email_box_type == 'imap':
        if not q.email_box_port: q.email_box_port = 143
        
        server = imaplib.IMAP4(q.email_box_host, q.email_box_port)
        server.login(q.email_box_user, q.email_box_pass)
        server.select(q.email_box_imap_folder)
        status, data = server.search(None, 'ALL')
        for num in data[0].split():
            status, data = server.fetch(num, '(RFC822)')
            ticket_from_message(message=data[0][1], queue=q)
            server.store(num, '+FLAGS', '\\Deleted')
        server.expunge()
        server.close()
        server.logout()

def ticket_from_message(message, queue):
    # 'message' must be an RFC822 formatted message.
    msg = message
    message = email.message_from_string(msg)
    subject = message.get('subject', _('Created from e-mail'))
    subject = subject.replace("Re: ", "").replace("Fw: ", "").strip()
    
    sender = message.get('from', _('Unknown Sender'))
    
    sender_email = parseaddr(sender)[1]
    if sender_email.startswith('postmaster'):
        sender_email = ''

    regex = re.compile("^\[[A-Za-z0-9]+-\d+\]")
    if regex.match(subject):
        # This is a reply or forward.
        ticket = re.match(r"^\[(?P<queue>[A-Za-z0-9]+)-(?P<id>\d+)\]", subject).group('id')
    else:
        ticket = None
    counter = 0
    files = []
    for part in message.walk():
        if part.get_main_type() == 'multipart':
            continue
        
        name = part.get_param("name")
        
        if part.get_content_maintype() == 'text' and name == None:
            body = part.get_payload()
        else:
            if name == None:
                ext = mimetypes.guess_extension(part.get_content_type())
                name = "part-%i%s" % (counter, ext)
            files.append({'filename': name, 'content': part.get_payload(decode=True), 'type': part.get_content_type()})

        counter += 1
    
    now = datetime.now()

    if ticket:
        try:
            t = Ticket.objects.get(id=ticket)
            new = False
        except:
            ticket = None

    priority = 3

    smtp_priority = message.get('priority', '')
    smtp_importance = message.get('importance', '')

    high_priority_types = ('high', 'important', '1', 'urgent')

    if smtp_priority in high_priority_types or smtp_importance in high_priority_types:
        priority = 2

    if ticket == None:
        t = Ticket(
            title=subject,
            queue=queue,
            submitter_email=sender_email,
            created=now,
            description=body,
            priority=priority,
        )
        t.save()
        new = True
        update = ''
        
    context = {
        'ticket': t,
        'queue': queue,
    }

    if new:

        if sender_email:
            send_templated_mail('newticket_submitter', context, recipients=sender_email, sender=queue.from_address, fail_silently=True)

        if queue.new_ticket_cc:
            send_templated_mail('newticket_cc', context, recipients=queue.new_ticket_cc, sender=queue.from_address, fail_silently=True)
        
        if queue.updated_ticket_cc and queue.updated_ticket_cc != queue.new_ticket_cc:
            send_templated_mail('newticket_cc', context, recipients=queue.updated_ticket_cc, sender=queue.from_address, fail_silently=True)

    else:
        update = _(' (Updated)')

        if t.assigned_to:
            send_templated_mail('updated_owner', context, recipients=t.assigned_to.email, sender=queue.from_address, fail_silently=True)

        if queue.updated_ticket_cc:
            send_templated_mail('updated_cc', context, recipients=queue.updated_ticket_cc, sender=queue.from_address, fail_silently=True)

    f = FollowUp(
        ticket = t,
        title = _('E-Mail Received from %s' % sender_email),
        date = datetime.now(),
        public = True,
        comment = body,
    )
    f.save()

    print " [%s-%s] %s%s" % (t.queue.slug, t.id, t.title, update)

    for file in files:
        filename = file['filename'].replace(' ', '_')
        a = Attachment(followup=f, filename=filename, mime_type=file['type'], size=len(file['content']))
        a.save_file_file(file['filename'], file['content'])
        a.save()
        print "    - %s" % file['filename']
    
if __name__ == '__main__':
    process_email()
