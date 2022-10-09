"""
Django Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. Copyright 2018 Timothy Hobbs. All Rights Reserved.
See LICENSE for details.
"""

# import base64


from bs4 import BeautifulSoup
from datetime import timedelta
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Q
from django.utils import encoding, timezone
from django.utils.translation import gettext as _
import email
from email.message import Message
from email.utils import getaddresses
from email_reply_parser import EmailReplyParser
from helpdesk import settings
from helpdesk.exceptions import DeleteIgnoredTicketException, IgnoreTicketException
from helpdesk.lib import process_attachments, safe_template_context
from helpdesk.models import FollowUp, IgnoreEmail, Queue, Ticket
import imaplib
import logging
import mimetypes
import os
from os.path import isfile, join
import poplib
import re
import socket
import ssl
import sys
from time import ctime
import typing
from typing import List, Tuple


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
        try:
            ticket = object_from_message(message=full_message, queue=q, logger=logger)
        except IgnoreTicketException:
            logger.warn(
                "Message %s was ignored and will be left on POP3 server" % msgNum)
        except DeleteIgnoredTicketException:
            logger.warn(
                "Message %s was ignored and deleted from POP3 server" % msgNum)
            server.dele(msgNum)
        else:
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
        data = server.search(None, 'NOT', 'DELETED')[1]
        if data:
            msgnums = data[0].split()
            logger.info("Received %d messages from IMAP server" % len(msgnums))
            for num in msgnums:
                logger.info("Processing message %s" % num)
                data = server.fetch(num, '(RFC822)')[1]
                full_message = encoding.force_str(data[0][1], errors='replace')
                try:
                    ticket = object_from_message(message=full_message, queue=q, logger=logger)
                except IgnoreTicketException:
                    logger.warn("Message %s was ignored and will be left on IMAP server" % num)
                except DeleteIgnoredTicketException:
                    server.store(num, '+FLAGS', '\\Deleted')
                    logger.warn("Message %s was ignored and deleted from IMAP server" % num)
                except TypeError as te:
                    # Log the error with stacktrace to help identify what went wrong
                    logger.error(f"Unexpected error processing message: {te}", exc_info=True)
                else:
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
                try:
                    ticket = object_from_message(message=full_message, queue=q, logger=logger)
                except IgnoreTicketException:
                    logger.warn("Message %d was ignored and will be left in local directory", i)
                except DeleteIgnoredTicketException:
                    os.unlink(m)
                    logger.warn("Message %d was ignored and deleted local directory", i)
                else:
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
    from helpdesk.views.staff import subscribe_to_ticket_updates, User

    new_ticket_ccs = []
    for __, cced_email in cc_list:

        cced_email = cced_email.strip()
        if cced_email == ticket.queue.email_address:
            continue

        user = None

        try:
            user = User.objects.get(email=cced_email)  # @UndefinedVariable
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

    try:
        attached = process_attachments(f, files)
    except ValidationError as e:
        logger.error(str(e))
    else:
        for att_file in attached:
            logger.info(
                "Attachment '%s' (with size %s) successfully added to ticket from email.",
                att_file[0], att_file[1].size
            )

    context = safe_template_context(ticket)

    new_ticket_ccs = []
    new_ticket_ccs.append(create_ticket_cc(ticket, to_list + cc_list))

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


def get_ticket_id_from_subject_slug(
    queue_slug: str,
    subject: str,
    logger: logging.Logger
) -> typing.Optional[int]:
    """Get a ticket id from the subject string

    Performs a match on the subject using the queue_slug as reference,
    returning the ticket id if a match is found.
    """
    matchobj = re.match(r".*\[" + queue_slug + r"-(?P<id>\d+)\]", subject)
    ticket_id = None
    if matchobj:
        # This is a reply or forward.
        ticket_id = matchobj.group('id')
        logger.info("Matched tracking ID %s-%s" % (queue_slug, ticket_id))
    else:
        logger.info("No tracking ID matched.")
    return ticket_id


def add_file_if_always_save_incoming_email_message(
    files_,
    message: str
) -> None:
    """When `settings.HELPDESK_ALWAYS_SAVE_INCOMING_EMAIL_MESSAGE` is `True`
    add a file to the files_ list"""
    if getattr(django_settings, 'HELPDESK_ALWAYS_SAVE_INCOMING_EMAIL_MESSAGE', False):
        # save message as attachment in case of some complex markup renders
        # wrong
        files_.append(
            SimpleUploadedFile(
                _("original_message.eml").replace(
                    ".eml",
                    timezone.localtime().strftime("_%d-%m-%Y_%H:%M") + ".eml"
                ),
                str(message).encode("utf-8"),
                'text/plain'
            )
        )


def get_encoded_body(body: str) -> str:
    try:
        return body.encode('ascii').decode('unicode_escape')
    except UnicodeEncodeError:
        return body


def get_body_from_fragments(body) -> str:
    """Gets a body from the fragments, joined by a double line break"""
    return "\n\n".join(f.content for f in EmailReplyParser.read(body).fragments)


def get_email_body_from_part_payload(part) -> str:
    """Gets an decoded body from the payload part, if the decode fails,
    returns without encoding"""
    try:
        return encoding.smart_str(
            part.get_payload(decode=True)
        )
    except UnicodeDecodeError:
        return encoding.smart_str(
            part.get_payload(decode=False)
        )


def attempt_body_extract_from_html(message: str) -> str:
    mail = BeautifulSoup(str(message), "html.parser")
    beautiful_body = mail.find('body')
    body = None
    full_body = None
    if beautiful_body:
        try:
            body = beautiful_body.text
            full_body = body
        except AttributeError:
            pass
    if not body:
        body = ""
    return body, full_body


def extract_part_data(
        part: Message,
        counter: int,
        ticket_id: int,
        files: List,
        logger: logging.Logger
) -> Tuple[str, str]:
    name = part.get_filename()
    if name:
        name = email.utils.collapse_rfc2231_value(name)
    part_body = None
    part_full_body = None
    if part.get_content_maintype() == 'text' and name is None:
        if part.get_content_subtype() == 'plain':
            part_body = part.get_payload(decode=True)
            # https://github.com/django-helpdesk/django-helpdesk/issues/732
            if part['Content-Transfer-Encoding'] == '8bit' and part.get_content_charset() == 'utf-8':
                part_body = part_body.decode('unicode_escape')
            part_body = decodeUnknown(part.get_content_charset(), part_body)
            # have to use django_settings here so overwriting it works in tests
            # the default value is False anyway
            if ticket_id is None and getattr(django_settings, 'HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL', False):
                # first message in thread, we save full body to avoid
                # losing forwards and things like that
                part_full_body = get_body_from_fragments(part_body)
                part_body = EmailReplyParser.parse_reply(part_body)
            else:
                # second and other reply, save only first part of the
                # message
                part_body = EmailReplyParser.parse_reply(part_body)
                part_full_body = part_body
            # workaround to get unicode text out rather than escaped text
            part_body = get_encoded_body(part_body)
            logger.debug("Discovered plain text MIME part")
        else:
            email_body = get_email_body_from_part_payload(part)

            if not part_body and not part_full_body:
                # no text has been parsed so far - try such deep parsing
                # for some messages
                altered_body = email_body.replace(
                    "</p>", "</p>\n").replace("<br", "\n<br")
                mail = BeautifulSoup(str(altered_body), "html.parser")
                part_full_body = mail.get_text()

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
            name = f"part-{counter}{ext}"
        else:
            name = f"part-{counter}_{name}"

        files.append(SimpleUploadedFile(name, part.get_payload(decode=True), mimetypes.guess_type(name)[0]))
        logger.debug("Found MIME attachment %s", name)
    return part_body, part_full_body


def object_from_message(message: str,
                        queue: Queue,
                        logger: logging.Logger
                        ) -> Ticket:
    # 'message' must be an RFC822 formatted message to correctly parse.
    message_obj = email.message_from_string(message)

    subject = message_obj.get('subject', _('Comment from e-mail'))
    subject = decode_mail_headers(
        decodeUnknown(message_obj.get_charset(), subject))
    for affix in STRIPPED_SUBJECT_STRINGS:
        subject = subject.replace(affix, "")
    subject = subject.strip()

    # TODO: Should really be assigning a properly formatted fake email.
    #       Check if anything relies on this being a "real name" formatted string if no sender is found on message_obj.
    #       Also not sure it should be accepting emails from unknown senders
    sender_email = _('Unknown Sender')
    sender_hdr = message_obj.get('from')
    if sender_hdr:
        # Parse the header which extracts the first email address in the list if more than one
        # The parseaddr method returns a tuple in the form <real name> <email address>
        # Only need the actual email address from the tuple not the "real name"
        # Since the spec requires that all email addresses are ASCII, they will not be encoded
        sender_email = email.utils.parseaddr(sender_hdr)[1]

    for ignore in IgnoreEmail.objects.filter(Q(queues=queue) | Q(queues__isnull=True)):
        if ignore.test(sender_email):
            raise IgnoreTicketException() if ignore.keep_in_mailbox else DeleteIgnoredTicketException()

    ticket_id: typing.Optional[int] = get_ticket_id_from_subject_slug(
        queue.slug,
        subject,
        logger
    )

    body = None
    full_body = None
    counter = 0
    files = []

    for part in message_obj.walk():
        if part.get_content_maintype() == 'multipart':
            continue
        # See email.message_obj.Message.get_filename()
        part_body, part_full_body = extract_part_data(part, counter, ticket_id, files, logger)
        if part_body:
            body = part_body
            full_body = part_full_body
        counter += 1

    if not body:
        body, full_body = attempt_body_extract_from_html(message_obj)

    add_file_if_always_save_incoming_email_message(files, message_obj)

    smtp_priority = message_obj.get('priority', '')
    smtp_importance = message_obj.get('importance', '')
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

    return create_object_from_email_message(message_obj, ticket_id, payload, files, logger=logger)
