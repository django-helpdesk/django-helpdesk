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
from __future__ import unicode_literals

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
from django.template.defaultfilters import linebreaksbr

from email_reply_parser import EmailReplyParser


from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.translation import ugettext as _
from django.utils import encoding, six, timezone

from helpdesk import settings
from helpdesk.lib import send_templated_mail, safe_template_context, process_attachments
from helpdesk.models import Queue, Ticket, TicketCC, FollowUp, IgnoreEmail

import logging

from base.models import Notification

User = get_user_model()


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

        try:
            handler = logging.FileHandler(join(logdir, q.slug + '_get_email.log'))
            logger.addHandler(handler)

            if not q.email_box_last_check:
                q.email_box_last_check = timezone.now() - timedelta(minutes=30)

            queue_time_delta = timedelta(minutes=q.email_box_interval or 0)

            if (q.email_box_last_check + queue_time_delta) < timezone.now():
                process_queue(q, logger=logger)
                q.email_box_last_check = timezone.now()
                q.save()
        finally:
            try:
                handler.close()
            except Exception as e:
                logging.exception(e)
            try:
                logger.removeHandler(handler)
            except Exception as e:
                logging.exception(e)


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
    elif six.PY2:
        socket.socket = socket._socketobject

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
        logger.info("Received %d messages from POP3 server" % len(messagesInfo))

        for msgRaw in messagesInfo:
            if six.PY3 and type(msgRaw) is bytes:
                # in py3, msgRaw may be a bytes object, decode to str
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

            if six.PY2:
                full_message = encoding.force_text("\n".join(server.retr(msgNum)[1]), errors='replace')
            else:
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
                except TypeError as e:
                    logger.error(e)
                    ticket = None  # hotfix. Need to work out WHY.
                if ticket:
                    server.store(num, '+FLAGS', '\\Deleted')
                    logger.info("Successfully processed message %s, deleted from IMAP server" % num)
                else:
                    logger.warn("Message %s was not successfully processed, and will be left on IMAP server" % num)

        server.expunge()
        server.close()
        server.logout()

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


def decode_unknown(charset, string):
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
    return ' '.join([
        str(msg, encoding=charset, errors='replace') if charset else str(msg) for msg, charset in decoded
    ])


def ticket_from_message(message, queue, logger):
    # 'message' must be an RFC822 formatted message.
    message = email.message_from_string(message) if six.PY3 else email.message_from_string(message.encode('utf-8'))
    subject = message.get('subject', _('Comment from e-mail'))
    subject = decode_mail_headers(decode_unknown(message.get_charset(), subject))
    for affix in STRIPPED_SUBJECT_STRINGS:
        subject = subject.replace(affix, "")
    subject = subject.strip()

    sender = message.get('from', _('Unknown Sender'))
    sender = decode_mail_headers(decode_unknown(message.get_charset(), sender))
    logger.debug('sender = "%s"' % sender)
    # to address bug #832, we wrap all the text in front of the email address in
    # double quotes by using replace() on the email string. Then,
    # take first item of list, second item of tuple is the actual email address.
    # Note that the replace won't work on just an email with no real name,
    # but the getaddresses() function seems to be able to handle just unclosed quotes
    # correctly. Not ideal, but this seems to work for now.
    if sender[0] != '"':
        sender = '\"' + sender.replace('<', '\" <')
    sender_email = email.utils.getaddresses([sender])[0][1]
    logger.debug('sender_email = "%s"' % sender_email)

    cc = message.get_all('cc', None)
    logger.debug('CC list before :')
    logger.debug(cc)
    if cc:
        cc = {mail for name, mail in email.utils.getaddresses(cc)}
        logger.debug('CC list after :')
        logger.debug(cc)
        # first, fixup the encoding if necessary
        # cc = [decode_mail_headers(decodeUnknown(message.get_charset(), x)) for x in cc]
        # get_all checks if multiple CC headers, but individual emails may be comma separated too
        # tempcc = []
        # for hdr in cc:
        #     tempcc.extend(hdr.split(','))
        # use a set to ensure no duplicates
        # cc = set([x.strip() for x in tempcc])

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
        ticket_id = matchobj.group('id')
        logger.info("Matched tracking ID %s-%s" % (queue.slug, ticket_id))
    else:
        logger.info("No tracking ID matched.")
        ticket_id = None

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
            if part.get_content_subtype() == 'plain' and body is None:
                body = part.get_payload(decode=True)
                # https://github.com/django-helpdesk/django-helpdesk/issues/732
                if part['Content-Transfer-Encoding'] == '8bit' and part.get_content_charset() == 'utf-8':
                    body = body.decode('unicode_escape')
                body = decode_unknown(part.get_content_charset(), body)
                body = EmailReplyParser.parse_reply(body)
                # workaround to get unicode text out rather than escaped text
                try:
                    body = body.encode('ascii').decode('unicode_escape')
                except UnicodeEncodeError:
                    body.encode('utf-8')
                # Add <br> tag for new lines
                body = linebreaksbr(body)
                logger.debug("Discovered plain text MIME part")
            else:
                try:
                    email_body = encoding.smart_text(part.get_payload(decode=True))
                except UnicodeDecodeError as e:
                    logger.debug("UnicodeDecodeError on body decoding : %s" % e)
                    email_body = encoding.smart_text(part.get_payload(decode=False))
                payload = """
                <html>
                <head>
                <meta charset="utf-8"/>
                </head>
                %s
                </html>""" % email_body
                files.append(
                    SimpleUploadedFile(_("email_html_body.html"), payload.encode("utf-8"), 'text/html')
                )
                logger.debug("Discovered HTML MIME part and attached to ticket")
        else:
            if not name:
                ext = mimetypes.guess_extension(part.get_content_type())
                name = "part-%i%s" % (counter, ext)
            payload = part.get_payload()
            if isinstance(payload, list):
                payload = payload.pop().as_string()
            payloadToWrite = payload
            # check version of python to ensure use of only the correct error type
            if six.PY2:
                non_b64_err = binascii.Error
            else:
                non_b64_err = TypeError
            try:
                logger.debug("Try to base64 decode the attachment payload")
                if six.PY2:
                    payloadToWrite = base64.decodestring(payload)
                else:
                    payloadToWrite = base64.decodebytes(payload)
            except non_b64_err:
                logger.debug("Payload was not base64 encoded, using raw bytes")
                payloadToWrite = payload
            files.append(SimpleUploadedFile(name, part.get_payload(decode=True), mimetypes.guess_type(name)[0]))
            logger.debug("Found MIME attachment %s" % name)

        counter += 1

    if not body:
        mail = BeautifulSoup(str(message), "html.parser")
        beautiful_body = mail.find('body')
        body = ""
        if beautiful_body:
            try:
                body = beautiful_body.text
            except AttributeError:
                pass

    ticket = None
    new = True
    if ticket_id:
        try:
            ticket = Ticket.objects.get(id=ticket_id)
        except Ticket.DoesNotExist:
            logger.info("Tracking ID %s-%s not associated with existing ticket. Creating new ticket." % (queue.slug, ticket_id))
        else:
            logger.info("Found existing ticket with Tracking ID %s-%s" % (ticket.queue.slug, ticket.id))

            # Check if the ticket has been merged to another ticket
            if ticket.merged_to:
                logger.info("Ticket was merged to %s-%s. Using this to add follow up."
                            % (ticket.merged_to.queue.slug, ticket.merged_to.id))
                # Use the merged ticket for the next operations
                ticket = ticket.merged_to

            # Check if ticket is not too old to get reopened
            if ticket.is_closed_and_too_old():
                logger.info("Ticket is too old to get reopened. Creating new ticket.")
                # Add reference to original ticket at the top of the body
                body = "<p>Ouverture d'un nouveau ticket car #%s était fermé depuis plus de 15 jours.</p><hr>%s" \
                       % (ticket.id, body)
                # Update the subject to better show the link with previous ticket
                subject = '%s - Suite ticket #%s' % (
                    subject.replace(('[%s-%s]' % (ticket.queue.slug, ticket.id)), '').strip(),
                    ticket.id
                )
                ticket = None
            else:
                new = False
                # Reopen ticket if it was closed
                if ticket.status == Ticket.CLOSED_STATUS:
                    logger.info("Ticket has been reopened.")
                    ticket.status = Ticket.REOPENED_STATUS
                    ticket.save()

    smtp_priority = message.get('priority', '')
    smtp_importance = message.get('importance', '')
    high_priority_types = {'high', 'important', '1', 'urgent'}
    priority = 2 if high_priority_types & {smtp_priority, smtp_importance} else 3

    if new:
        if settings.QUEUE_EMAIL_BOX_UPDATE_ONLY:
            return None
        # Try to find corresponding user thanks to submitter email
        search_users = User.objects.filter(email__iexact=sender_email)
        customer_contact = None
        customer = None
        if len(search_users) == 1:
            customer_contact = search_users.first()
            logger.debug("Found associated user with mail address %s : %s" % (sender_email, customer_contact))
            # Associate customer if the user belongs to only one customer
            search_customers = customer_contact.groups.exclude(customer=None)
            if len(search_customers) == 1:
                customer = search_customers.first().customer
                logger.debug("Found associated customer : %s" % customer)
        ticket = Ticket.objects.create(
            title=subject,
            queue=queue,
            submitter_email=sender_email,
            created=timezone.now(),
            description=body,
            priority=priority,
            customer_contact=customer_contact,
            customer=customer
        )
        logger.debug("Created new ticket %s-%s" % (ticket.queue.slug, ticket.id))

    # Create TicketCC for ticket
    if ticket and cc:
        # get list of currently CC'd emails
        current_cc = ticket.ticketcc_set.all()
        current_cc_emails = [x.email for x in current_cc if x.email]
        # get emails of any Users CC'd to email, if defined
        # (some Users may not have an associated email, e.g, when using LDAP)
        current_cc_users = [x.user.email for x in current_cc if x.user and x.user.email]
        # ensure submitter, assigned user, queue email not added
        other_emails = [queue.email_address]
        if ticket.submitter_email:
            other_emails.append(ticket.submitter_email)
        if ticket.customer_contact:
            other_emails.append(ticket.customer_contact.email)
        if ticket.assigned_to:
            other_emails.append(ticket.assigned_to.email)
        current_cc = set(current_cc_emails + current_cc_users + other_emails)
        # first, add any User not previously CC'd (as identified by User's email)
        all_user_emails = set([x.email for x in User.objects.exclude(email=None)])
        users_not_currently_ccd = all_user_emails.difference(set(current_cc))
        users_to_cc = cc.intersection(users_not_currently_ccd)
        for user_email in users_to_cc:
            try:
                ticket.ticketcc_set.create(
                    user=User.objects.get(email=user_email),
                    can_view=True,
                    can_update=False
                )
            except User.MultipleObjectsReturned:
                logger.error('Multiple users has this email address : %s' % user_email)
                pass
        # then add remaining emails alphabetically, makes testing easy
        new_cc = cc.difference(current_cc).difference(all_user_emails)
        new_cc = sorted(list(new_cc))
        for ccemail in new_cc:
            ticket.ticketcc_set.create(
                email=ccemail,
                can_view=True,
                can_update=False
            )

    f = FollowUp(
        ticket=ticket,
        title='E-Mail reçu de %s' % sender_email,
        date=timezone.now(),
        public=True,
        comment=body,
    )

    if ticket.status == Ticket.REOPENED_STATUS:
        f.new_status = Ticket.REOPENED_STATUS
        f.title = 'Ticket rouvert par un mail reçu de %s' % sender_email

    f.save()
    logger.debug("Created new FollowUp for Ticket")

    if six.PY2:
        logger.info(("[%s-%s] %s" % (ticket.queue.slug, ticket.id, ticket.title,)).encode('ascii', 'replace'))
    elif six.PY3:
        logger.info("[%s-%s] %s" % (ticket.queue.slug, ticket.id, ticket.title,))

    logger.debug('Files to attach :')
    logger.debug(files)
    attached = process_attachments(f, files)
    for att_file in attached:
        logger.info("Attachment '%s' (with size %s) successfully added to ticket from email." % (att_file[0], att_file[1].size))

    context = safe_template_context(ticket)

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
        # Send notification to technical service
        Notification.objects.create_for_technical_service(
            message="Un nouveau ticket vient d'être ouvert par mail : %s" % ticket,
            module=Notification.TICKET,
            link_redirect=ticket.get_absolute_url()
        )
    else:
        context['ticket']['comment'] = f.comment
        if ticket.assigned_to:
            send_templated_mail(
                'updated_owner',
                context,
                recipients=ticket.assigned_to.email,
                sender=queue.from_address,
                fail_silently=True,
            )
            # Send Phoenix notification to the user assigned to the ticket
            Notification.objects.create(
                module=Notification.TICKET,
                message="Une nouvelle réponse a été ajouté par mail sur votre ticket %s" % ticket,
                link_redirect=ticket.get_absolute_url(),
                user_list=[ticket.assigned_to]
            )
        else:
            # Send notification to technical service
            Notification.objects.create_for_technical_service(
                message="Une réponse vient d'être ajoutée au ticket par mail : %s" % ticket,
                module=Notification.TICKET,
                link_redirect=ticket.get_absolute_url()
            )
        if queue.updated_ticket_cc:
            send_templated_mail(
                'updated_cc',
                context,
                recipients=queue.updated_ticket_cc,
                sender=queue.from_address,
                fail_silently=True,
            )
        # Send mail to submitter if the follow up was made by someone else
        if sender_email not in ticket.get_submitter_emails():
            send_templated_mail(
                'updated_submitter',
                context,
                recipients=ticket.get_submitter_emails(),
                sender=queue.from_address,
                fail_silently=True,
            )
        # copy email to all those CC'd to this particular ticket
        for cc in ticket.ticketcc_set.all():
            # don't duplicate email to assignee
            address_to_ignore = [sender_email]
            if ticket.assigned_to and ticket.assigned_to.email:
                address_to_ignore.append(ticket.assigned_to.email)
            if cc.email_address not in address_to_ignore:
                send_templated_mail(
                    'updated_cc',
                    context,
                    recipients=cc.email_address,
                    sender=queue.from_address,
                    fail_silently=True,
                )

    return ticket


if __name__ == '__main__':
    process_email()
