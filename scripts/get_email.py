import poplib
import imaplib
from datetime import datetime, timedelta
import email, mimetypes, re
from email.Utils import parseaddr
from helpdesk.models import Queue,Ticket
from helpdesk.lib import send_multipart_mail

def process_email():
    for q in Queue.objects.filter(email_box_type__isnull=False):
        if not q.email_box_last_check: q.email_box_last_check = datetime.now()-timedelta(minutes=30)
        if not q.email_box_interval: q.email_box_interval = 0

        if (q.email_box_last_check + timedelta(minutes=q.email_box_interval)) > datetime.now():
            continue
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

        q.email_box_last_check = datetime.now()
        q.save()

def ticket_from_message(message, queue):
    # 'message' must be an RFC822 formatted message.
    msg = message
    message = email.message_from_string(msg)
    subject = message.get('subject', 'Created from e-mail')
    subject = subject.replace("Re: ", "").replace("Fw: ", "").strip()
    
    sender = message.get('from', 'Unknown Sender')
    
    sender_email = parseaddr(message.get('from', 'Unknown Sender'))[1]

    regex = re.compile("^\[\d+\]")
    if regex.match(subject):
        # This is a reply or forward.
        ticket = re.match(r"^\[(?P<id>\d+)\]", subject).group('id')
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
        
        context = {
            'ticket': t,
            'queue': queue,
        }

        if sender_email:
            send_multipart_mail('helpdesk/emails/submitter_newticket', context, '%s %s' % (t.ticket, t.title), sender_email, queue.from_address)
    
    print " [%s-%s] %s" % (t.queue.slug, t.id, t.title)

    #for file in files:
        #data = file['content']
        #filename = file['filename'].replace(' ', '_')
        #type = file['type']
        #a = Attachment(followup=f, filename=filename, mimetype=type, size=len(data))
        #a.save()
        #print "    - %s" % file['filename']
    
if __name__ == '__main__':
    process_email()
