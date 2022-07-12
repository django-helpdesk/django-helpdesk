"""
Django Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. Copyright 2018 Timothy Hobbs. All Rights Reserved.
See LICENSE for details.
"""
# import base64
import email
import imaplib
import logging
import mimetypes
import os
import poplib
import re
import socket
import ssl
import sys
from datetime import timedelta
from email.utils import getaddresses
from os.path import isfile, join
from time import ctime

from bs4 import BeautifulSoup
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Q
from django.utils import encoding, timezone
from django.utils.translation import gettext as _
from email_reply_parser import EmailReplyParser

from helpdesk import settings
from helpdesk.lib import safe_template_context, process_attachments
from helpdesk.models import Queue, Ticket, TicketCC, FollowUp, IgnoreEmail


# import User model, which may be a custom model
User = get_user_model()


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
            # disable all handlers so messages go to nowhere
            logger.handlers = []
            logger.propagate = False
        if quiet:
            logger.propagate = False  # do not propagate to root logger that would log to console

        # Log messages to specific file only if the queue has it configured
        if (q.logging_type in logging_types) and q.logging_dir:  # if it's enabled and the dir is set
            log_file_handler = logging.FileHandler(
                join(q.logging_dir, q.slug + '_get_email.log'))
            logger.addHandler(log_file_handler)
        else:
            log_file_handler = None

        try:
            if not q.email_box_last_check:
                q.email_box_last_check = timezone.now() - timedelta(minutes=30)

            queue_time_delta = timedelta(minutes=q.email_box_interval or 0)
            if (q.email_box_last_check + queue_time_delta) < timezone.now():
                process_queue(q, logger=logger)
                q.email_box_last_check = timezone.now()
                q.save()
        finally:
            # we must close the file handler correctly if it's created
            try:
                if log_file_handler:
                    log_file_handler.close()
            except Exception as e:
                logging.exception(e)
            try:
                if log_file_handler:
                    logger.removeHandler(log_file_handler)
            except Exception as e:
                logging.exception(e)


def pop3_sync(q, logger, server):
    server.getwelcome()
    try:
        server.stls()
    except Exception:
        logger.warning(
            "POP3 StartTLS failed or unsupported. Connection will be unencrypted.")
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
            full_message = "\n".join([elm.decode('utf-8')
                                      for elm in raw_content])
        else:
            full_message = encoding.force_str(
                "\n".join(raw_content), errors='replace')
        ticket = object_from_message(
            message=full_message, queue=q, logger=logger)

        if ticket:
            server.dele(msgNum)
            logger.info(
                "Successfully processed message %s, deleted from POP3 server" % msgNum)
        else:
            logger.warn(
                "Message %s was not successfully processed, and will be left on POP3 server" % msgNum)

    server.quit()


def imap_sync(q, logger, server):
    try:
        try:
            server.starttls()
        except Exception:
            logger.warning(
                "IMAP4 StartTLS unsupported or failed. Connection will be unencrypted.")
        server.login(q.email_box_user or
                     settings.QUEUE_EMAIL_BOX_USER,
                     q.email_box_pass or
                     settings.QUEUE_EMAIL_BOX_PASSWORD)
        server.select(q.email_box_imap_folder)
    except imaplib.IMAP4.abort:
        logger.error(
            "IMAP login failed. Check that the server is accessible and that "
            "the username and password are correct."
        )
        server.logout()
        sys.exit()
    except ssl.SSLError:
        logger.error(
            "IMAP login failed due to SSL error. This is often due to a timeout. "
            "Please check your connection and try again."
        )
        server.logout()
        sys.exit()

    try:
        status, data = server.search(None, 'NOT', 'DELETED')
        if data:
            msgnums = data[0].split()
            logger.info("Received %d messages from IMAP server" % len(msgnums))
            for num in msgnums:
                logger.info("Processing message %s" % num)
                status, data = server.fetch(num, '(RFC822)')
                full_message = encoding.force_str(data[0][1], errors='replace')
                try:
                    ticket = object_from_message(
                        message=full_message, queue=q, logger=logger)
                except TypeError:
                    ticket = None  # hotfix. Need to work out WHY.
                if ticket:
                    server.store(num, '+FLAGS', '\\Deleted')
                    logger.info(
                        "Successfully processed message %s, deleted from IMAP server" % num)
                else:
                    logger.warn(
                        "Message %s was not successfully processed, and will be left on IMAP server" % num)
    except imaplib.IMAP4.error:
        logger.error(
            "IMAP retrieve failed. Is the folder '%s' spelled correctly, and does it exist on the server?",
            q.email_box_imap_folder
        )

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
        mail = [join(mail_dir, f)
                for f in os.listdir(mail_dir) if isfile(join(mail_dir, f))]
        logger.info("Found %d messages in local mailbox directory" % len(mail))

        logger.info("Found %d messages in local mailbox directory" % len(mail))
        for i, m in enumerate(mail, 1):
            logger.info("Processing message %d" % i)
            with open(m, 'r') as f:
                full_message = encoding.force_str(f.read(), errors='replace')
                ticket = object_from_message(
                    message=full_message, queue=q, logger=logger)
            if ticket:
                logger.info(
                    "Successfully processed message %d, ticket/comment created.", i)
                try:
                    # delete message file if ticket was successful
                    os.unlink(m)
                except OSError as e:
                    logger.error(
                        "Unable to delete message %d (%s).", i, str(e))
                else:
                    logger.info("Successfully deleted message %d.", i)
            else:
                logger.warn(
                    "Message %d was not successfully processed, and will be left in local directory", i)


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
    return u' '.join([
        str(msg, encoding=charset, errors='replace') if charset else str(msg)
        for msg, charset
        in decoded
    ])


def is_autoreply(message):
    """
    Accepting message as something with .get(header_name) method
    Returns True if it's likely to be auto-reply or False otherwise
    So we don't start mail loops
    """
    any_if_this = [
        False if not message.get(
            "Auto-Submitted") else message.get("Auto-Submitted").lower() != "no",
        True if message.get("X-Auto-Response-Suppress") in ("DR",
                                                            "AutoReply", "All") else False,
        message.get("List-Id"),
        message.get("List-Unsubscribe"),
    ]
    return any(any_if_this)


def create_ticket_cc(ticket, cc_list):

    if not cc_list:
        return []

    # Local import to deal with non-defined / circular reference problem
    from helpdesk.views.staff import User, subscribe_to_ticket_updates

    new_ticket_ccs = []
    for cced_name, cced_email in cc_list:

        cced_email = cced_email.strip()
        if cced_email == ticket.queue.email_address:
            continue

        user = None

        try:
            user = User.objects.get(email=cced_email)
        except User.DoesNotExist:
            pass

        try:
            ticket_cc = subscribe_to_ticket_updates(
                ticket=ticket, user=user, email=cced_email)
            new_ticket_ccs.append(ticket_cc)
        except ValidationError:
            pass

    return new_ticket_ccs


def create_object_from_email_message(message, ticket_id, payload, files, logger):

    ticket, previous_followup, new = None, None, False
    now = timezone.now()

    queue = payload['queue']
    sender_email = payload['sender_email']

    to_list = getaddresses(message.get_all('To', []))
    cc_list = getaddresses(message.get_all('Cc', []))

    message_id = message.get('Message-Id')
    in_reply_to = message.get('In-Reply-To')

    if message_id:
        message_id = message_id.strip()

    if in_reply_to:
        in_reply_to = in_reply_to.strip()

    if in_reply_to is not None:
        try:
            queryset = FollowUp.objects.filter(
                message_id=in_reply_to).order_by('-date')
            if queryset.count() > 0:
                previous_followup = queryset.first()
                ticket = previous_followup.ticket
        except FollowUp.DoesNotExist:
            pass  # play along. The header may be wrong

    if previous_followup is None and ticket_id is not None:
        try:
            ticket = Ticket.objects.get(id=ticket_id)
        except Ticket.DoesNotExist:
            ticket = None
        else:
            new = False
            # Check if the ticket has been merged to another ticket
            if ticket.merged_to:
                logger.info("Ticket has been merged to %s" %
                            ticket.merged_to.ticket)
                # Use the ticket in which it was merged to for next operations
                ticket = ticket.merged_to

    # New issue, create a new <Ticket> instance
    if ticket is None:
        if not settings.QUEUE_EMAIL_BOX_UPDATE_ONLY:
            ticket = Ticket.objects.create(
                title=payload['subject'],
                queue=queue,
                submitter_email=sender_email,
                created=now,
                description=payload['body'],
                priority=payload['priority'],
            )
            ticket.save()
            logger.debug("Created new ticket %s-%s" %
                         (ticket.queue.slug, ticket.id))

            new = True

    # Old issue being re-opened
    elif ticket.status == Ticket.CLOSED_STATUS:
        ticket.status = Ticket.REOPENED_STATUS
        ticket.save()

    f = FollowUp(
        ticket=ticket,
        title=_('E-Mail Received from %(sender_email)s' %
                {'sender_email': sender_email}),
        date=now,
        public=True,
        comment=payload.get('full_body', payload['body']) or "",
        message_id=message_id
    )

    if ticket.status == Ticket.REOPENED_STATUS:
        f.new_status = Ticket.REOPENED_STATUS
        f.title = _('Ticket Re-Opened by E-Mail Received from %(sender_email)s' %
                    {'sender_email': sender_email})

    f.save()
    logger.debug("Created new FollowUp for Ticket")

    logger.info("[%s-%s] %s" % (ticket.queue.slug, ticket.id, ticket.title,))

    attached = process_attachments(f, files)
    for att_file in attached:
        logger.info(
            "Attachment '%s' (with size %s) successfully added to ticket from email.",
            att_file[0], att_file[1].size
        )

    context = safe_template_context(ticket)

    new_ticket_ccs = []
    new_ticket_ccs.append(create_ticket_cc(ticket, to_list + cc_list))

    notifications_to_be_sent = [sender_email]

    if queue.enable_notifications_on_email_events and len(notifications_to_be_sent):

        ticket_cc_list = TicketCC.objects.filter(
            ticket=ticket).all().values_list('email', flat=True)

        for email_address in ticket_cc_list:
            notifications_to_be_sent.append(email_address)

    autoreply = is_autoreply(message)
    if autoreply:
        logger.info(
            "Message seems to be auto-reply, not sending any emails back to the sender")
    else:
        # send mail to appropriate people now depending on what objects
        # were created and who was CC'd
        # Add auto-reply headers because it's an auto-reply and we must
        extra_headers = {
            'In-Reply-To': message_id,
            "Auto-Submitted": "auto-replied",
            "X-Auto-Response-Suppress": "All",
            "Precedence": "auto_reply",
        }
        if new:
            ticket.send(
                {'submitter': ('newticket_submitter', context),
                 'new_ticket_cc': ('newticket_cc', context),
                 'ticket_cc': ('newticket_cc', context)},
                fail_silently=True,
                extra_headers=extra_headers,
            )
        else:
            context.update(comment=f.comment)
            ticket.send(
                {'submitter': ('newticket_submitter', context),
                 'assigned_to': ('updated_owner', context)},
                fail_silently=True,
                extra_headers=extra_headers,
            )
            if queue.enable_notifications_on_email_events:
                ticket.send(
                    {'ticket_cc': ('updated_cc', context)},
                    fail_silently=True,
                    extra_headers=extra_headers,
                )

    return ticket


def object_from_message(message, queue, logger):
    # 'message' must be an RFC822 formatted message.
    message = email.message_from_string(message)

    subject = message.get('subject', _('Comment from e-mail'))
    subject = decode_mail_headers(
        decodeUnknown(message.get_charset(), subject))
    for affix in STRIPPED_SUBJECT_STRINGS:
        subject = subject.replace(affix, "")
    subject = subject.strip()

    sender = message.get('from', _('Unknown Sender'))
    sender = decode_mail_headers(decodeUnknown(message.get_charset(), sender))

    # to address bug #832, we wrap all the text in front of the email address in
    # double quotes by using replace() on the email string. Then,
    # take first item of list, second item of tuple is the actual email address.
    # Note that the replace won't work on just an email with no real name,
    # but the getaddresses() function seems to be able to handle just unclosed quotes
    # correctly. Not ideal, but this seems to work for now.
    sender_email = email.utils.getaddresses(
        ['\"' + sender.replace('<', '\" <')])[0][1]

    cc = message.get_all('cc', None)
    if cc:
        # first, fixup the encoding if necessary
        cc = [decode_mail_headers(decodeUnknown(
            message.get_charset(), x)) for x in cc]
        # get_all checks if multiple CC headers, but individual emails may be
        # comma separated too
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
    full_body = None
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
                body = part.get_payload(decode=True)
                # https://github.com/django-helpdesk/django-helpdesk/issues/732
                if part['Content-Transfer-Encoding'] == '8bit' and part.get_content_charset() == 'utf-8':
                    body = body.decode('unicode_escape')
                body = decodeUnknown(part.get_content_charset(), body)
                # have to use django_settings here so overwritting it works in tests
                # the default value is False anyway
                if ticket is None and getattr(django_settings, 'HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL', False):
                    # first message in thread, we save full body to avoid
                    # losing forwards and things like that
                    body_parts = []
                    for f in EmailReplyParser.read(body).fragments:
                        body_parts.append(f.content)
                    full_body = '\n\n'.join(body_parts)
                    body = EmailReplyParser.parse_reply(body)
                else:
                    # second and other reply, save only first part of the
                    # message
                    body = EmailReplyParser.parse_reply(body)
                    full_body = body
                # workaround to get unicode text out rather than escaped text
                try:
                    body = body.encode('ascii').decode('unicode_escape')
                except UnicodeEncodeError:
                    body.encode('utf-8')
                logger.debug("Discovered plain text MIME part")
            else:
                try:
                    email_body = encoding.smart_str(
                        part.get_payload(decode=True))
                except UnicodeDecodeError:
                    email_body = encoding.smart_str(
                        part.get_payload(decode=False))

                if not body and not full_body:
                    # no text has been parsed so far - try such deep parsing
                    # for some messages
                    altered_body = email_body.replace(
                        "</p>", "</p>\n").replace("<br", "\n<br")
                    mail = BeautifulSoup(str(altered_body), "html.parser")
                    full_body = mail.get_text()

                if "<body" not in email_body:
                    email_body = f"<body>{email_body}</body>"

                payload = (
                    '<html>'
                    '<head>'
                    '<meta charset="utf-8" />'
                    '</head>'
                    '%s'
                    '</html>'
                ) % email_body
                files.append(
                    SimpleUploadedFile(
                        _("email_html_body.html"), payload.encode("utf-8"), 'text/html')
                )
                logger.debug("Discovered HTML MIME part")
        else:
            if not name:
                ext = mimetypes.guess_extension(part.get_content_type())
                name = "part-%i%s" % (counter, ext)
            else:
                name = ("part-%i_" % counter) + name

            # # FIXME: this code gets the paylods, then does something with it and then completely ignores it
            # # writing the part.get_payload(decode=True) instead; and then the payload variable is
            # # replaced by some dict later.
            # # the `payloadToWrite` has been also ignored so was commented
            # payload = part.get_payload()
            # if isinstance(payload, list):
            #     payload = payload.pop().as_string()
            # # payloadToWrite = payload
            # # check version of python to ensure use of only the correct error type
            # non_b64_err = TypeError
            # try:
            #     logger.debug("Try to base64 decode the attachment payload")
            #     # payloadToWrite = base64.decodebytes(payload)
            # except non_b64_err:
            #     logger.debug("Payload was not base64 encoded, using raw bytes")
            #     # payloadToWrite = payload
            files.append(SimpleUploadedFile(name, part.get_payload(
                decode=True), mimetypes.guess_type(name)[0]))
            logger.debug("Found MIME attachment %s" % name)

        counter += 1

    if not body:
        mail = BeautifulSoup(str(message), "html.parser")
        beautiful_body = mail.find('body')
        if beautiful_body:
            try:
                body = beautiful_body.text
                full_body = body
            except AttributeError:
                pass
        if not body:
            body = ""

    if getattr(django_settings, 'HELPDESK_ALWAYS_SAVE_INCOMING_EMAIL_MESSAGE', False):
        # save message as attachment in case of some complex markup renders
        # wrong
        files.append(
            SimpleUploadedFile(
                _("original_message.eml").replace(
                    ".eml",
                    timezone.localtime().strftime("_%d-%m-%Y_%H:%M") + ".eml"
                ),
                str(message).encode("utf-8"),
                'text/plain'
            )
        )

    smtp_priority = message.get('priority', '')
    smtp_importance = message.get('importance', '')
    high_priority_types = {'high', 'important', '1', 'urgent'}
    priority = 2 if high_priority_types & {
        smtp_priority, smtp_importance} else 3

    payload = {
        'body': body,
        'full_body': full_body or body,
        'subject': subject,
        'queue': queue,
        'sender_email': sender_email,
        'priority': priority,
        'files': files,
    }

    return create_object_from_email_message(message, ticket, payload, files, logger=logger)
