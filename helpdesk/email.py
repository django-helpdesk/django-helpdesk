#!/usr/bin/python
"""
Django Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. Copyright 2018 Timothy Hobbs. All Rights Reserved.
See LICENSE for details.

scripts/get_email.py - Designed to be run from cron, this script checks the
                       POP and IMAP boxes, or a local mailbox directory,
                       defined for the queues within a
                       helpdesk, creating tickets from the new messages (or
                       adding to existing tickets if needed)
"""

from datetime import timedelta
import base64
import binascii
import email
import imaplib
import mimetypes
from os import listdir, unlink
from os.path import isfile, join
import poplib
import re
import socket
import ssl
import sys
from time import ctime

from bs4 import BeautifulSoup

from email_reply_parser import EmailReplyParser

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.translation import ugettext as _
from django.utils import encoding, timezone

from helpdesk import settings
from helpdesk.lib import safe_template_context, process_attachments
from helpdesk.models import Queue, Ticket, TicketCC, FollowUp, IgnoreEmail
from django.contrib.auth.models import User

import logging


STRIPPED_SUBJECT_STRINGS = [
    "Re: ",
    "Fw: ",
    "RE: ",
    "FW: ",
    "Automatic reply: ",
]


def process_email(quiet=False):
    for q in Queue.objects.filter(
            email_box_type__isnull=False,
            allow_email_submission=True):

        logger = logging.getLogger('django.helpdesk.queue.' + q.slug)
        logging_types = {
            'info': logging.INFO,
            'warn': logging.WARN,
            'error': logging.ERROR,
            'crit': logging.CRITICAL,
            'debug': logging.DEBUG,
        }
        if q.logging_type in logging_types:
            logger.setLevel(logging_types[q.logging_type])
        elif not q.logging_type or q.logging_type == 'none':
            logging.disable(logging.CRITICAL)  # disable all messages
        if quiet:
            logger.propagate = False  # do not propagate to root logger that would log to console
        logdir = q.logging_dir or '/var/log/helpdesk/'
        handler = logging.FileHandler(join(logdir, q.slug + '_get_email.log'))
        logger.addHandler(handler)

        if not q.email_box_last_check:
            q.email_box_last_check = timezone.now() - timedelta(minutes=30)

        queue_time_delta = timedelta(minutes=q.email_box_interval or 0)

        if (q.email_box_last_check + queue_time_delta) < timezone.now():
            process_queue(q, logger=logger)
            q.email_box_last_check = timezone.now()
            q.save()


def pop3_sync(q, logger, server):
    server.getwelcome()
    server.user(q.email_box_user or settings.QUEUE_EMAIL_BOX_USER)
    server.pass_(q.email_box_pass or settings.QUEUE_EMAIL_BOX_PASSWORD)

    messagesInfo = server.list()[1]
    logger.info("Received %d messages from POP3 server" % len(messagesInfo))

    for msgRaw in messagesInfo:
        if type(msgRaw) is bytes:
            try:
                msg = msgRaw.decode("utf-8")
            except UnicodeError:
                # if couldn't decode easily, just leave it raw
                msg = msgRaw
        else:
            # already a str
            msg = msgRaw
        msgNum = msg.split(" ")[0]
        logger.info("Processing message %s" % msgNum)

        raw_content = server.retr(msgNum)[1]
        if type(raw_content[0]) is bytes:
            full_message = "\n".join([elm.decode('utf-8') for elm in raw_content])
        else:
            full_message = encoding.force_text("\n".join(raw_content), errors='replace')
        ticket = ticket_from_message(message=full_message, queue=q, logger=logger)

        if ticket:
            server.dele(msgNum)
            logger.info("Successfully processed message %s, deleted from POP3 server" % msgNum)
        else:
            logger.warn("Message %s was not successfully processed, and will be left on POP3 server" % msgNum)

    server.quit()


def imap_sync(q, logger, server):
    try:
        server.login(q.email_box_user or
                     settings.QUEUE_EMAIL_BOX_USER,
                     q.email_box_pass or
                     settings.QUEUE_EMAIL_BOX_PASSWORD)
        server.select(q.email_box_imap_folder)
    except imaplib.IMAP4.abort:
        logger.error("IMAP login failed. Check that the server is accessible and that the username and password are correct.")
        server.logout()
        sys.exit()
    except ssl.SSLError:
        logger.error("IMAP login failed due to SSL error. This is often due to a timeout. Please check your connection and try again.")
        server.logout()
        sys.exit()

    try:
        status, data = server.search(None, 'NOT', 'DELETED')
    except imaplib.IMAP4.error:
        logger.error("IMAP retrieve failed. Is the folder '%s' spelled correctly, and does it exist on the server?" % q.email_box_imap_folder)
    if data:
        msgnums = data[0].split()
        logger.info("Received %d messages from IMAP server" % len(msgnums))
        for num in msgnums:
            logger.info("Processing message %s" % num)
            status, data = server.fetch(num, '(RFC822)')
            full_message = encoding.force_text(data[0][1], errors='replace')
            try:
                ticket = ticket_from_message(message=full_message, queue=q, logger=logger)
            except TypeError:
                ticket = None  # hotfix. Need to work out WHY.
            if ticket:
                server.store(num, '+FLAGS', '\\Deleted')
                logger.info("Successfully processed message %s, deleted from IMAP server" % num)
            else:
                logger.warn("Message %s was not successfully processed, and will be left on IMAP server" % num)

    server.expunge()
    server.close()
    server.logout()


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

    email_box_type = settings.QUEUE_EMAIL_BOX_TYPE or q.email_box_type

    mail_defaults = {
        'pop3': {
            'ssl': {
                'port': 995,
                'init': poplib.POP3_SSL,
            },
            'insecure': {
                'port': 110,
                'init': poplib.POP3,
            },
            'sync': pop3_sync,
        },
        'imap': {
            'ssl': {
                'port': 993,
                'init': imaplib.IMAP4_SSL,
            },
            'insecure': {
                'port': 143,
                'init': imaplib.IMAP4,
            },
            'sync': imap_sync
        }
    }
    if email_box_type in mail_defaults:
        encryption = 'insecure'
        if q.email_box_ssl or settings.QUEUE_EMAIL_BOX_SSL:
            encryption = 'ssl'
        if not q.email_box_port:
            q.email_box_port = mail_defaults[email_box_type][encryption]['port']

        server = mail_defaults[email_box_type][encryption]['init'](
            q.email_box_host or settings.QUEUE_EMAIL_BOX_HOST,
            int(q.email_box_port)
        )
        logger.info("Attempting %s server login" % email_box_type.upper())
        mail_defaults[email_box_type]['sync'](q, logger, server)

    elif email_box_type == 'local':
        mail_dir = q.email_box_local_dir or '/var/lib/mail/helpdesk/'
        mail = [join(mail_dir, f) for f in listdir(mail_dir) if isfile(join(mail_dir, f))]
        logger.info("Found %d messages in local mailbox directory" % len(mail))

        logger.info("Found %d messages in local mailbox directory" % len(mail))
        for i, m in enumerate(mail, 1):
            logger.info("Processing message %d" % i)
            with open(m, 'r') as f:
                full_message = encoding.force_text(f.read(), errors='replace')
                ticket = ticket_from_message(message=full_message, queue=q, logger=logger)
            if ticket:
                logger.info("Successfully processed message %d, ticket/comment created." % i)
                try:
                    unlink(m)  # delete message file if ticket was successful
                except OSError:
                    logger.error("Unable to delete message %d." % i)
                else:
                    logger.info("Successfully deleted message %d." % i)
            else:
                logger.warn("Message %d was not successfully processed, and will be left in local directory" % i)


def decodeUnknown(charset, string):
    if type(string) is not str:
        if not charset:
            try:
                return str(string, encoding='utf-8', errors='replace')
            except UnicodeError:
                return str(string, encoding='iso8859-1', errors='replace')
        return str(string, encoding=charset, errors='replace')
    return string


def decode_mail_headers(string):
    decoded = email.header.decode_header(string)
    return u' '.join([str(msg, encoding=charset, errors='replace') if charset else str(msg) for msg, charset in decoded])


def ticket_from_message(message, queue, logger):
    # 'message' must be an RFC822 formatted message.
    message = email.message_from_string(message)
    subject = message.get('subject', _('Comment from e-mail'))
    subject = decode_mail_headers(decodeUnknown(message.get_charset(), subject))
    for affix in STRIPPED_SUBJECT_STRINGS:
        subject = subject.replace(affix, "")
    subject = subject.strip()

    sender = message.get('from', _('Unknown Sender'))
    sender = decode_mail_headers(decodeUnknown(message.get_charset(), sender))
    sender_email = email.utils.parseaddr(sender)[1]

    cc = message.get_all('cc', None)
    if cc:
        # first, fixup the encoding if necessary
        cc = [decode_mail_headers(decodeUnknown(message.get_charset(), x)) for x in cc]
        # get_all checks if multiple CC headers, but individual emails may be comma separated too
        tempcc = []
        for hdr in cc:
            tempcc.extend(hdr.split(','))
        # use a set to ensure no duplicates
        cc = set([x.strip() for x in tempcc])

    for ignore in IgnoreEmail.objects.filter(Q(queues=queue) | Q(queues__isnull=True)):
        if ignore.test(sender_email):
            if ignore.keep_in_mailbox:
                # By returning 'False' the message will be kept in the mailbox,
                # and the 'True' will cause the message to be deleted.
                return False
            return True

    matchobj = re.match(r".*\[" + queue.slug + r"-(?P<id>\d+)\]", subject)
    if matchobj:
        # This is a reply or forward.
        ticket = matchobj.group('id')
        logger.info("Matched tracking ID %s-%s" % (queue.slug, ticket))
    else:
        logger.info("No tracking ID matched.")
        ticket = None

    body = None
    counter = 0
    files = []

    for part in message.walk():
        if part.get_content_maintype() == 'multipart':
            continue

        name = part.get_param("name")
        if name:
            name = email.utils.collapse_rfc2231_value(name)

        if part.get_content_maintype() == 'text' and name is None:
            if part.get_content_subtype() == 'plain':
                body = EmailReplyParser.parse_reply(
                    decodeUnknown(part.get_content_charset(), part.get_payload(decode=True))
                )
                # workaround to get unicode text out rather than escaped text
                try:
                    body = body.encode('ascii').decode('unicode_escape')
                except UnicodeEncodeError:
                    body.encode('utf-8')
                logger.debug("Discovered plain text MIME part")
            else:
                files.append(
                    SimpleUploadedFile(_("email_html_body.html"), encoding.smart_bytes(part.get_payload()), 'text/html')
                )
                logger.debug("Discovered HTML MIME part")
        else:
            if not name:
                ext = mimetypes.guess_extension(part.get_content_type())
                name = "part-%i%s" % (counter, ext)
            payload = part.get_payload()
            if isinstance(payload, list):
                payload = payload.pop().as_string()
            payloadToWrite = payload
            # check version of python to ensure use of only the correct error type
            non_b64_err = TypeError
            try:
                logger.debug("Try to base64 decode the attachment payload")
                payloadToWrite = base64.decodebytes(payload)
            except non_b64_err:
                logger.debug("Payload was not base64 encoded, using raw bytes")
                payloadToWrite = payload
            files.append(SimpleUploadedFile(name, part.get_payload(decode=True), mimetypes.guess_type(name)[0]))
            logger.debug("Found MIME attachment %s" % name)

        counter += 1

    if not body:
        mail = BeautifulSoup(part.get_payload(), "lxml")
        beautiful_body = mail.find('body')
        if beautiful_body:
            try:
                body = beautiful_body.text
            except AttributeError:
                pass
        if not body:
            body = mail.text

    if ticket:
        try:
            t = Ticket.objects.get(id=ticket)
        except Ticket.DoesNotExist:
            logger.info("Tracking ID %s-%s not associated with existing ticket. Creating new ticket." % (queue.slug, ticket))
            ticket = None
        else:
            logger.info("Found existing ticket with Tracking ID %s-%s" % (t.queue.slug, t.id))
            if t.status == Ticket.CLOSED_STATUS:
                t.status = Ticket.REOPENED_STATUS
                t.save()
            new = False

    smtp_priority = message.get('priority', '')
    smtp_importance = message.get('importance', '')
    high_priority_types = {'high', 'important', '1', 'urgent'}
    priority = 2 if high_priority_types & {smtp_priority, smtp_importance} else 3

    if ticket is None:
        if settings.QUEUE_EMAIL_BOX_UPDATE_ONLY:
            return None
        new = True
        t = Ticket.objects.create(
            title=subject,
            queue=queue,
            submitter_email=sender_email,
            created=timezone.now(),
            description=body,
            priority=priority,
        )
        logger.debug("Created new ticket %s-%s" % (t.queue.slug, t.id))

    if cc:
        # get list of currently CC'd emails
        current_cc = TicketCC.objects.filter(ticket=ticket)
        current_cc_emails = [x.email for x in current_cc if x.email]
        # get emails of any Users CC'd to email, if defined
        # (some Users may not have an associated email, e.g, when using LDAP)
        current_cc_users = [x.user.email for x in current_cc if x.user and x.user.email]
        # ensure submitter, assigned user, queue email not added
        other_emails = [queue.email_address]
        if t.submitter_email:
            other_emails.append(t.submitter_email)
        if t.assigned_to:
            other_emails.append(t.assigned_to.email)
        current_cc = set(current_cc_emails + current_cc_users + other_emails)
        # first, add any User not previously CC'd (as identified by User's email)
        all_users = User.objects.all()
        all_user_emails = set([x.email for x in all_users])
        users_not_currently_ccd = all_user_emails.difference(set(current_cc))
        users_to_cc = cc.intersection(users_not_currently_ccd)
        for user in users_to_cc:
            tcc = TicketCC.objects.create(
                ticket=t,
                user=User.objects.get(email=user),
                can_view=True,
                can_update=False
            )
            tcc.save()
        # then add remaining emails alphabetically, makes testing easy
        new_cc = cc.difference(current_cc).difference(all_user_emails)
        new_cc = sorted(list(new_cc))
        for ccemail in new_cc:
            tcc = TicketCC.objects.create(
                ticket=t,
                email=ccemail.replace('\n', ' ').replace('\r', ' '),
                can_view=True,
                can_update=False
            )
            tcc.save()

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

    logger.info("[%s-%s] %s" % (t.queue.slug, t.id, t.title,))

    attached = process_attachments(f, files)
    for att_file in attached:
        logger.info("Attachment '%s' (with size %s) successfully added to ticket from email." % (att_file[0], att_file[1].size))

    context = safe_template_context(t)

    if new:
        t.send(
            {'submitter': ('newticket_submitter', context),
             'new_ticket_cc': ('newticket_cc', context),
             'ticket_cc': ('newticket_cc', context)},
            fail_silently=True,
        )
    else:
        context.update(comment=f.comment)
        t.send(
            {'assigned_to': ('updated_owner', context),
             'ticket_cc': ('updated_cc', context)},
            fail_silently=True,
        )

    return t
