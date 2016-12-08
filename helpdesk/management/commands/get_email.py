#!/usr/bin/python
"""
Jutda Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

scripts/get_email.py - Designed to be run from cron, this script checks the
                       POP and IMAP boxes, or a local mailbox directory,
                       defined for the queues within a
                       helpdesk, creating tickets from the new messages (or
                       adding to existing tickets if needed)
"""

import email
import imaplib
import mimetypes
import poplib
import re
import socket
from os import listdir, unlink
from os.path import isfile, join

from datetime import timedelta
from email.header import decode_header
from email.utils import parseaddr, collapse_rfc2231_value
from optparse import make_option

from email_reply_parser import EmailReplyParser

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.translation import ugettext as _
from django.utils import six, timezone

from helpdesk import settings
from helpdesk.lib import send_templated_mail, safe_template_context
from helpdesk.models import Queue, Ticket, FollowUp, Attachment, IgnoreEmail

import logging
from time import ctime


STRIPPED_SUBJECT_STRINGS = [
    "Re: ",
    "Fw: ",
    "RE: ",
    "FW: ",
    "Automatic reply: ",
]


class Command(BaseCommand):

    def __init__(self):
        BaseCommand.__init__(self)

    help = 'Process django-helpdesk queues and process e-mails via POP3/IMAP or ' \
           'from a local mailbox directory as required, feeding them into the helpdesk.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--quiet',
            action='store_true',
            dest='quiet',
            default=False,
            help='Hide details about each queue/message as they are processed',
        )

    def handle(self, *args, **options):
        quiet = options.get('quiet', False)
        process_email(quiet=quiet)


def process_email(quiet=False):
    for q in Queue.objects.filter(
            email_box_type__isnull=False,
            allow_email_submission=True):

        logger = logging.getLogger('django.helpdesk.queue.' + q.slug)
        if not q.logging_type or q.logging_type == 'none':
            logging.disable(logging.CRITICAL)  # disable all messages
        elif q.logging_type == 'info':
            logger.setLevel(logging.INFO)
        elif q.logging_type == 'warn':
            logger.setLevel(logging.WARN)
        elif q.logging_type == 'error':
            logger.setLevel(logging.ERROR)
        elif q.logging_type == 'crit':
            logger.setLevel(logging.CRITICAL)
        elif q.logging_type == 'debug':
            logger.setLevel(logging.DEBUG)
        if quiet:
            logger.propagate = False  # do not propagate to root logger that would log to console
        logdir = q.logging_dir or '/var/log/helpdesk/'
        handler = logging.FileHandler(logdir + q.slug + '_get_email.log')
        logger.addHandler(handler)

        if not q.email_box_last_check:
            q.email_box_last_check = timezone.now() - timedelta(minutes=30)

        if not q.email_box_interval:
            q.email_box_interval = 0

        queue_time_delta = timedelta(minutes=q.email_box_interval)

        if (q.email_box_last_check + queue_time_delta) > timezone.now():
            continue

        process_queue(q, logger=logger)

        q.email_box_last_check = timezone.now()
        q.save()


def process_queue(q, logger):
    logger.info("***** %s: Begin processing mail for django-helpdesk" % ctime())

    if q.socks_proxy_type and q.socks_proxy_host and q.socks_proxy_port:
        try:
            import socks
        except ImportError:
            no_socks_msg = "Queue has been configured with proxy settings, " \
                           "but no socks library was installed. Try to " \
                           "install PySocks via PyPI."
            logger.error(no_socks_msg)
            raise ImportError(no_socks_msg)

        proxy_type = {
            'socks4': socks.SOCKS4,
            'socks5': socks.SOCKS5,
        }.get(q.socks_proxy_type)

        socks.set_default_proxy(proxy_type=proxy_type,
                                addr=q.socks_proxy_host,
                                port=q.socks_proxy_port)
        socket.socket = socks.socksocket
    else:
        if six.PY2:
            socket.socket = socket._socketobject
        elif six.PY3:
            import _socket
            socket.socket = _socket.socket

    email_box_type = settings.QUEUE_EMAIL_BOX_TYPE or q.email_box_type

    if email_box_type == 'pop3':
        if q.email_box_ssl or settings.QUEUE_EMAIL_BOX_SSL:
            if not q.email_box_port:
                q.email_box_port = 995
            server = poplib.POP3_SSL(q.email_box_host or
                                     settings.QUEUE_EMAIL_BOX_HOST,
                                     int(q.email_box_port))
        else:
            if not q.email_box_port:
                q.email_box_port = 110
            server = poplib.POP3(q.email_box_host or
                                 settings.QUEUE_EMAIL_BOX_HOST,
                                 int(q.email_box_port))

        logger.info("Attempting POP3 server login")

        server.getwelcome()
        server.user(q.email_box_user or settings.QUEUE_EMAIL_BOX_USER)
        server.pass_(q.email_box_pass or settings.QUEUE_EMAIL_BOX_PASSWORD)

        messagesInfo = server.list()[1]
        logger.info("Received %s messages from POP3 server" % str(len(messagesInfo)))

        for msg in messagesInfo:
            msgNum = msg.split(" ")[0]
            logger.info("Processing message %s" % str(msgNum))

            full_message = "\n".join(server.retr(msgNum)[1])
            ticket = ticket_from_message(message=full_message, queue=q, logger=logger)

            if ticket:
                server.dele(msgNum)
                logger.info("Successfully processed message %s, deleted from POP3 server" % str(msgNum))
            else:
                logger.warn("Message %s was not successfully processed, and will be left on POP3 server" % str(msgNum))

        server.quit()

    elif email_box_type == 'imap':
        if q.email_box_ssl or settings.QUEUE_EMAIL_BOX_SSL:
            if not q.email_box_port:
                q.email_box_port = 993
            server = imaplib.IMAP4_SSL(q.email_box_host or
                                       settings.QUEUE_EMAIL_BOX_HOST,
                                       int(q.email_box_port))
        else:
            if not q.email_box_port:
                q.email_box_port = 143
            server = imaplib.IMAP4(q.email_box_host or
                                   settings.QUEUE_EMAIL_BOX_HOST,
                                   int(q.email_box_port))

        logger.info("Attempting IMAP server login")

        server.login(q.email_box_user or
                     settings.QUEUE_EMAIL_BOX_USER,
                     q.email_box_pass or
                     settings.QUEUE_EMAIL_BOX_PASSWORD)
        server.select(q.email_box_imap_folder)

        status, data = server.search(None, 'NOT', 'DELETED')
        if data:
            msgnums = data[0].split()
            logger.info("Received %s messages from IMAP server" % str(len(msgnums)))
            for num in msgnums:
                logger.info("Processing message %s" % str(num))
                status, data = server.fetch(num, '(RFC822)')
                ticket = ticket_from_message(message=data[0][1], queue=q, logger=logger)
                if ticket:
                    server.store(num, '+FLAGS', '\\Deleted')
                    logger.info("Successfully processed message %s, deleted from IMAP server" % str(num))
                else:
                    logger.warn("Message %s was not successfully processed, and will be left on IMAP server" % str(num))

        server.expunge()
        server.close()
        server.logout()

    elif email_box_type == 'local':
        mail_dir = q.email_box_local_dir or '/var/lib/mail/helpdesk/'
        mail = [join(mail_dir, f) for f in listdir(mail_dir) if isfile(join(mail_dir, f))]
        logger.info("Found %s messages in local mailbox directory" % str(len(mail)))
        for m in mail:
            logger.info("Processing message %s" % str(m))
            with open(m, 'r') as f:
                ticket = ticket_from_message(message=f.read(), queue=q, logger=logger)
                if ticket:
                    logger.info("Successfully processed message %s, ticket/comment created." % str(m))
                    try:
                        unlink(m)  # delete message file if ticket was successful
                        logger.info("Successfully deleted message %s." % str(m))
                    except:
                        logger.error("Unable to delete message %s." % str(m))
                else:
                    logger.warn("Message %s was not successfully processed, and will be left in local directory" % str(m))


def decodeUnknown(charset, string):
    if six.PY2:
        if not charset:
            try:
                return string.decode('utf-8', 'ignore')
            except:
                return string.decode('iso8859-1', 'ignore')
        return unicode(string, charset)
    elif six.PY3:
        if type(string) is not str:
            if not charset:
                try:
                    return str(string, encoding='utf-8', errors='replace')
                except:
                    return str(string, encoding='iso8859-1', errors='replace')
            return str(string, encoding=charset)
        return string


def decode_mail_headers(string):
    decoded = decode_header(string)
    if six.PY2:
        return u' '.join([unicode(msg, charset or 'utf-8') for msg, charset in decoded])
    elif six.PY3:
        return u' '.join([str(msg, encoding=charset, errors='replace') if charset else str(msg) for msg, charset in decoded])


def ticket_from_message(message, queue, logger):
    # 'message' must be an RFC822 formatted message.
    msg = message
    if six.PY2:
        message = email.message_from_string(msg)
    elif six.PY3:
        message = email.message_from_bytes(msg)
    subject = message.get('subject', _('Created from e-mail'))
    subject = decode_mail_headers(decodeUnknown(message.get_charset(), subject))
    for affix in STRIPPED_SUBJECT_STRINGS:
        subject = subject.replace(affix, "")
    subject = subject.strip()

    sender = message.get('from', _('Unknown Sender'))
    sender = decode_mail_headers(decodeUnknown(message.get_charset(), sender))

    sender_email = parseaddr(sender)[1]

    body_plain, body_html = '', ''

    for ignore in IgnoreEmail.objects.filter(Q(queues=queue) | Q(queues__isnull=True)):
        if ignore.test(sender_email):
            if ignore.keep_in_mailbox:
                # By returning 'False' the message will be kept in the mailbox,
                # and the 'True' will cause the message to be deleted.
                return False
            return True

    matchobj = re.match(r".*\[" + queue.slug + "-(?P<id>\d+)\]", subject)
    if matchobj:
        # This is a reply or forward.
        ticket = matchobj.group('id')
        logger.info("Matched tracking ID %s-%s" % (queue.slug, ticket))
    else:
        logger.info("No tracking ID matched.")
        ticket = None

    counter = 0
    files = []

    for part in message.walk():
        if part.get_content_maintype() == 'multipart':
            continue

        name = part.get_param("name")
        if name:
            name = collapse_rfc2231_value(name)

        if part.get_content_maintype() == 'text' and name is None:
            if part.get_content_subtype() == 'plain':
                body_plain = EmailReplyParser.parse_reply(
                    decodeUnknown(part.get_content_charset(), part.get_payload(decode=True)))
                logger.debug("Discovered plain text MIME part")
            else:
                body_html = part.get_payload(decode=True)
                logger.debug("Discovered HTML MIME part")
        else:
            if not name:
                ext = mimetypes.guess_extension(part.get_content_type())
                name = "part-%i%s" % (counter, ext)

            files.append({
                'filename': name,
                'content': part.get_payload(decode=True),
                'type': part.get_content_type()},
            )
            logger.debug("Found MIME attachment %s" % name)

        counter += 1

    if body_plain:
        body = body_plain
    else:
        body = _('No plain-text email body available. Please see attachment "email_html_body.html".')

    if body_html:
        files.append({
            'filename': _("email_html_body.html"),
            'content': body_html,
            'type': 'text/html',
        })

    now = timezone.now()

    if ticket:
        try:
            t = Ticket.objects.get(id=ticket)
            new = False
            logger.info("Found existing ticket with Tracking ID %s-%s" % (t.queue.slug, t.id))
        except Ticket.DoesNotExist:
            logger.info("Tracking ID %s-%s not associated with existing ticket. Creating new ticket." % (queue.slug, ticket))
            ticket = None

    priority = 3

    smtp_priority = message.get('priority', '')
    smtp_importance = message.get('importance', '')

    high_priority_types = ('high', 'important', '1', 'urgent')

    if smtp_priority in high_priority_types or smtp_importance in high_priority_types:
        priority = 2

    if ticket is None:
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
        logger.debug("Created new ticket %s-%s" % (t.queue.slug, t.id))

    elif t.status == Ticket.CLOSED_STATUS:
        t.status = Ticket.REOPENED_STATUS
        t.save()

    f = FollowUp(
        ticket=t,
        title=_('E-Mail Received from %(sender_email)s' % {'sender_email': sender_email}),
        date=timezone.now(),
        public=True,
        comment=body,
    )

    if t.status == Ticket.REOPENED_STATUS:
        f.new_status = Ticket.REOPENED_STATUS
        f.title = _('Ticket Re-Opened by E-Mail Received from %(sender_email)s' % {'sender_email': sender_email})

    f.save()
    logger.debug("Created new FollowUp for Ticket")

    if six.PY2:
        logger.info(("[%s-%s] %s" % (t.queue.slug, t.id, t.title,)).encode('ascii', 'replace'))
    elif six.PY3:
        logger.info("[%s-%s] %s" % (t.queue.slug, t.id, t.title,))

    for file in files:
        if file['content']:
            if six.PY2:
                filename = file['filename'].encode('ascii', 'replace').replace(' ', '_')
            elif six.PY3:
                filename = file['filename'].replace(' ', '_')
            filename = re.sub('[^a-zA-Z0-9._-]+', '', filename)
            logger.info("Found attachment '%s'" % filename)
            a = Attachment(
                followup=f,
                filename=filename,
                mime_type=file['type'],
                size=len(file['content']),
            )
            a.file.save(filename, ContentFile(file['content']), save=False)
            a.save()
            logger.info("Attachment '%s' successfully added to ticket." % filename)

    context = safe_template_context(t)

    if new:

        if sender_email:
            send_templated_mail(
                'newticket_submitter',
                context,
                recipients=sender_email,
                sender=queue.from_address,
                fail_silently=True,
            )

        if queue.new_ticket_cc:
            send_templated_mail(
                'newticket_cc',
                context,
                recipients=queue.new_ticket_cc,
                sender=queue.from_address,
                fail_silently=True,
            )

        if queue.updated_ticket_cc and queue.updated_ticket_cc != queue.new_ticket_cc:
            send_templated_mail(
                'newticket_cc',
                context,
                recipients=queue.updated_ticket_cc,
                sender=queue.from_address,
                fail_silently=True,
            )

    else:
        context.update(comment=f.comment)

        # if t.status == Ticket.REOPENED_STATUS:
        #     update = _(' (Reopened)')
        # else:
        #     update = _(' (Updated)')

        if t.assigned_to:
            send_templated_mail(
                'updated_owner',
                context,
                recipients=t.assigned_to.email,
                sender=queue.from_address,
                fail_silently=True,
            )

        if queue.updated_ticket_cc:
            send_templated_mail(
                'updated_cc',
                context,
                recipients=queue.updated_ticket_cc,
                sender=queue.from_address,
                fail_silently=True,
            )

    return t


if __name__ == '__main__':
    process_email()
