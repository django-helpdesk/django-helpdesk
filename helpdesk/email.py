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
from email import policy
from email.message import EmailMessage, MIMEPart
from email.utils import getaddresses
from email_reply_parser import EmailReplyParser
from helpdesk import settings
from helpdesk.exceptions import DeleteIgnoredTicketException, IgnoreTicketException
from helpdesk.lib import process_attachments, safe_template_context
from helpdesk.models import FollowUp, IgnoreEmail, Queue, Ticket
from helpdesk.signals import new_ticket_done, update_ticket_done
import imaplib
import logging
import mimetypes
import oauthlib.oauth2 as oauth2lib
import os
from os.path import isfile, join
import poplib
import re
import requests_oauthlib
import socket
import ssl
import sys
from time import ctime
import traceback
import typing
from typing import List


# import User model, which may be a custom model
User = get_user_model()

STRIPPED_SUBJECT_STRINGS = [
    "Re: ",
    "Fw: ",
    "RE: ",
    "FW: ",
    "Automatic reply: ",
]

# Allow a custom default attached email name for the HTML formatted email if one is found
HTML_EMAIL_ATTACHMENT_FILENAME = _("email_html_body.html")


def process_email(quiet: bool = False, debug_to_stdout: bool = False):
    if debug_to_stdout:
        print("Extracting email into queues...")
    q: Queue()  # Typing ahead of time for loop to make it more useful in an IDE
    for q in Queue.objects.filter(
            email_box_type__isnull=False,
            allow_email_submission=True):
        log_msg = f"Processing queue: {q.slug} Email address: {q.email_address}..."
        if debug_to_stdout:
            print(log_msg)
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
            if not q.email_box_last_check:
                q.email_box_last_check = timezone.now() - timedelta(minutes=30)
        try:
            queue_time_delta = timedelta(minutes=q.email_box_interval or 0)
            if (q.email_box_last_check + queue_time_delta) < timezone.now():
                process_queue(q, logger=logger)
                q.email_box_last_check = timezone.now()
                q.save()
                log_msg: str = f"Queue successfully processed: {q.slug}"
                logger.info(log_msg)
                if debug_to_stdout:
                    print(log_msg)
        except Exception as e:
            logger.error(f"Queue processing failed: {q.slug} -- {e}", exc_info=True)
            if debug_to_stdout:
                print(f"Queue processing failed: {q.slug}")
                print("-"*60)
                traceback.print_exc(file=sys.stdout)
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
    if debug_to_stdout:
        print("Email extraction into queues completed.")


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
            ticket = extract_email_metadata(message=full_message, queue=q, logger=logger)
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
                    ticket = extract_email_metadata(message=full_message, queue=q, logger=logger)
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


def imap_oauth_sync(q, logger, server):
    """
    IMAP eMail server with OAUTH authentication.
    Only tested against O365 implementation

    Uses HELPDESK OAUTH Dict in Settings.

    """

    try:
        logger.debug("Start Mailbox polling via IMAP OAUTH")

        client = oauth2lib.BackendApplicationClient(
            client_id=settings.HELPDESK_OAUTH["client_id"],
            scope=settings.HELPDESK_OAUTH["scope"],
        )

        oauth = requests_oauthlib.OAuth2Session(client=client)
        token = oauth.fetch_token(
            token_url=settings.HELPDESK_OAUTH["token_url"],
            client_id=settings.HELPDESK_OAUTH["client_id"],
            client_secret=settings.HELPDESK_OAUTH["secret"],
            include_client_id=True,
        )

        server.debug = settings.HELPDESK_IMAP_DEBUG_LEVEL
        # TODO: Perhaps store the authentication string template externally? Settings? Queue Table?
        server.authenticate(
            "XOAUTH2",
            lambda x: f"user={q.email_box_user}\x01auth=Bearer {token['access_token']}\x01\x01".encode(),
        )
        # Select the Inbound Mailbox folder
        server.select(q.email_box_imap_folder)

    except imaplib.IMAP4.abort as e1:
        logger.error(f"IMAP authentication failed in OAUTH: {e1}", exc_info=True)
        server.logout()
        sys.exit()

    except ssl.SSLError as e2:
        logger.error(
            f"IMAP login failed due to SSL error. (This is often due to a timeout): {e2}", exc_info=True
        )
        server.logout()
        sys.exit()

    try:
        data = server.search(None, 'NOT', 'DELETED')[1]
        if data:
            msgnums = data[0].split()
            logger.info(f"Found {len(msgnums)} message(s) on IMAP server")
            for num in msgnums:
                logger.info(f"Processing message {num}")
                data = server.fetch(num, '(RFC822)')[1]
                full_message = encoding.force_str(data[0][1], errors='replace')

                try:
                    ticket = extract_email_metadata(message=full_message, queue=q, logger=logger)

                except IgnoreTicketException as itex:
                    logger.warn(f"Message {num} was ignored. {itex}")

                except DeleteIgnoredTicketException:
                    server.store(num, '+FLAGS', '\\Deleted')
                    server.expunge()
                    logger.warn("Message %s was ignored and deleted from IMAP server" % num)

                except TypeError as te:
                    # Log the error with stacktrace to help identify what went wrong
                    logger.error(f"Unexpected error processing message: {te}", exc_info=True)

                else:
                    if ticket:
                        server.store(num, '+FLAGS', '\\Deleted')
                        server.expunge()
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
    # Purged Flagged Messages & Logout
    server.expunge()
    server.close()
    server.logout()


def process_queue(q, logger):
    logger.info(f"***** {ctime()}: Begin processing mail for django-helpdesk queue: {q.title}")

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
        },
        'oauth': {
            'ssl': {
                'port': 993,
                'init': imaplib.IMAP4_SSL,
            },
            'insecure': {
                'port': 143,
                'init': imaplib.IMAP4,
            },
            'sync': imap_oauth_sync
        },
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
                    ticket = extract_email_metadata(message=full_message, queue=q, logger=logger)
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
    if string and not isinstance(string, str):
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

    new_ticket_ccs = []
    from helpdesk.views.staff import subscribe_to_ticket_updates, User
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

    if settings.HELPDESK_ENABLE_ATTACHMENTS:
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
        send_info_email(message_id, f, ticket, context, queue, new)
    if new:
        # emit signal when a new ticket is created
        new_ticket_done.send(sender="create_object_from_email_message", ticket=ticket)
    else:
        # emit signal with followup when the ticket is updated
        update_ticket_done.send(sender="create_object_from_email_message", followup=f)
    return ticket


def send_info_email(message_id: str, f: FollowUp, ticket: Ticket, context: dict, queue: dict, new: bool):
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
            {'submitter': ('updated_submitter', context),
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


def mime_content_to_string(part: EmailMessage,) -> str:
    '''
    Extract the content from the MIME body part
    :param part: the MIME part to extract the content from
    '''
    content_bytes = part.get_payload(decode=True)
    charset = part.get_content_charset()
    # The default for MIME email is 7bit which requires special decoding to utf-8 so make sure
    # we handle the decoding correctly
    if part['Content-Transfer-Encoding'] in [None, '8bit', '7bit'] and (charset == 'utf-8' or charset is None):
        charset = "unicode_escape"
    content = decodeUnknown(charset, content_bytes)
    return content


def parse_email_content(mime_content: str, is_extract_full_email_msg: bool) -> str:
    if is_extract_full_email_msg:
        # Take the full content including encapsulated "forwarded" and "reply" sections
        return mime_content
    else:
        # Just get the primary part of the email and drop off any text below the actual response text
        return EmailReplyParser.parse_reply(mime_content)


def extract_email_message_content(
        part: MIMEPart,
        files: List,
        include_chained_msgs: bool,
) -> (str, str):
    '''
    Uses the get_body() method of the email package to extract the email message content.
    If there is an HTML version of the email message content then it is stored as an attachment.
    If there is a plain text part then that is used for storing the email content aginst the ticket.
    Otherwise if there is just an HTML part then the HTML is parsed to extract a simple text message.
    There is special handling for the case when a multipart/related part holds the message content when
    there are multiple attachments to the email.
    :param part: the base email MIME part to be searched
    :param files: any MIME parts to be attached are added to this list
    :param include_chained_msgs: flag to indicate if the entire email message content including past
           replies must be extracted
    '''
    message_part: MIMEPart = part.get_body()
    parent_part: MIMEPart = part
    content_type = message_part.get_content_type()
    # Handle the possibility of a related part formatted email
    if "multipart/related" == content_type:
        # We want the actual message text so try again on the related MIME part
        parent_part = message_part
        message_part = message_part.get_body(preferencelist=["html", "plain",])
        content_type = message_part.get_content_type()
    mime_content = None
    formatted_body = None  # Retain the original content by using a secondary variable if the HTML needs wrapping
    if "text/html" == content_type:
        # add the HTML message as an attachment wrapping if necessary
        mime_content = mime_content_to_string(message_part)
        if "<body" not in mime_content:
            formatted_body = f"<body>{mime_content}</body>"
        if "<html" not in mime_content:
            formatted_body = f"<html><head><meta charset=\"utf-8\" /></head>\
                               {mime_content if formatted_body is None else formatted_body}</html>"
        files.append(
            SimpleUploadedFile(
                HTML_EMAIL_ATTACHMENT_FILENAME,
                (mime_content if formatted_body is None else formatted_body).encode("utf-8"), 'text/html',
            )
        )
        # Try to get a plain part message
        plain_message_part = parent_part.get_body(preferencelist=["plain",])
        if plain_message_part:
            # Replace mime_content with the plain text part content
            mime_content = mime_content_to_string(plain_message_part)
            message_part = plain_message_part
            content_type = "text/plain"
        else:
            # Try to constitute the HTML response as plain text
            mime_content, _x = attempt_body_extract_from_html(
                mime_content if formatted_body is None else formatted_body)
    else:
        # Is either text/plain or some random content-type so just decode the part content and store as is
        mime_content = mime_content_to_string(message_part)
    # We should now have the mime content
    filtered_body = parse_email_content(mime_content, include_chained_msgs)
    if not filtered_body or "" == filtered_body.strip():
        # A unit test that has a different HTML content to plain text which seems an invalid case as email
        # tools should retain the HTML to be consistent with the plain text but manage this as a special case
        # Try to constitute the HTML response as plain text
        if formatted_body:
            filtered_body, _x = attempt_body_extract_from_html(formatted_body)
        else:
            filtered_body = mime_content
    # Only need the full message if the message_body excludes the chained messages
    return filtered_body, mime_content


def process_as_attachment(
        part: MIMEPart,
        counter: int,
        files: List,
        logger: logging.Logger
):
    name = part.get_filename()
    if name:
        name = f"part-{counter}_{email.utils.collapse_rfc2231_value(name)}"
    else:
        ext = mimetypes.guess_extension(part.get_content_type())
        name = f"part-{counter}{ext}"
    # Extract payload accounting for attached multiparts
    payload_bytes = part.as_bytes() if part.is_multipart() else part.get_payload(decode=True)
    files.append(SimpleUploadedFile(name, payload_bytes, mimetypes.guess_type(name)[0]))
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Processed MIME as attachment: %s", name)
    return


def extract_email_subject(email_msg: EmailMessage,) -> str:
    subject = email_msg.get('subject', _('Comment from e-mail'))
    subject = decode_mail_headers(
        decodeUnknown(email_msg.get_charset(), subject))
    for affix in STRIPPED_SUBJECT_STRINGS:
        subject = subject.replace(affix, "")
    return subject.strip()


def extract_attachments(
        target_part: MIMEPart,
        files: List,
        logger: logging.Logger,
        counter: int = 1,
        content_parts_excluded: bool = False,
) -> (int, bool):
    '''
    If the MIME part is a multipart and not identified as "inline" or "attachment" then
    iterate over the sub parts recursively.
    Otherwise extract MIME part content and add as an attachment.
    It will recursively descend as appropriate ensuring that all parts not part of the message content
    are added to the list of files to be attached. To cater for the possibility of text/plain and text/html parts
    that are further down in the multipart hierarchy than the ones that ones meant to provide that content,
    iterators are selectively used.
    :param part: the email MIME part to be processed
    :param files: any MIME part content or MIME parts to be attached are added to this list
    :param logger: the logger to use for this MIME part processing
    :param counter: the count of MIME parts added as attachment
    :param content_parts_excluded: the MIME part(s) that provided the message content have been excluded
    :returns the count of mime parts added as attachments and a boolean if the content parts have been excluded
    '''
    content_type = target_part.get_content_type()
    content_maintype = target_part.get_content_maintype()
    if "multipart" == content_maintype and target_part.get_content_disposition() not in ['inline', 'attachment']:
        # Cycle through all MIME parts in the email extracting the attachments that were not part of the message body
        # If this is a "related" multipart then we can use the message part excluder iterator directly
        if "multipart/related" == content_type:
            if content_parts_excluded:
                # This should really never happen in a properly constructed email message but...
                logger.warn(
                    "WARNING! Content type MIME parts have been excluded but a multipart/related has been encountered.\
                     There may be missing information in attachments.")
            else:
                content_parts_excluded = True
            # Use the iterator that automatically excludes message content parts
            for part in target_part.iter_attachments():
                counter, content_parts_excluded = extract_attachments(
                    part, files, logger, counter, content_parts_excluded)
        # The iterator must be different depending on whether we have already excluded message content parts
        else:
            # Content part might be 1 or 2 parts but will be at same level so track finding at least 1
            content_part_detected = False
            for part in target_part.iter_parts():
                if not content_parts_excluded and part.get_content_type() in ["text/plain", "text/html"]:
                    content_part_detected = True
                    continue
                # Recurse into the part to process embedded parts
                counter, content_parts_excluded = extract_attachments(
                    part, files, logger, counter, content_parts_excluded)
            # If we have found 1 or more content parts then flag that the content parts have been ommitted
            # to ensure that other text/* parts are attached
            if content_part_detected:
                content_parts_excluded = True
    else:
        process_as_attachment(target_part, counter, files, logger)
        counter = counter + 1
    return (counter, content_parts_excluded)


def extract_email_metadata(message: str,
                           queue: Queue,
                           logger: logging.Logger
                           ) -> Ticket:
    '''
    Extracts the text/plain  mime part if there is one as the ticket description and
    stores the text/html part as an attachment if it is present.
    If no text/plain  part is present then it will try to use the text/html part if
    it is present as the ticket description by removing the HTML formatting.
    If neither a text/plain or text/html is present then it will use the first text/*
    MIME part that it finds as the ticket description.
    By default it will always take only the actual message and drop any chained messages
    from replies.
    The HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL settings can force the entire message to be
    stored in the ticket if it is a new ticket by setting it to True.
    In this scenario, if it is a reply that is a forwarded message with no actual message,
    then the description will be sourced from the text/html part and the forwarded message
    will be in the FollowUp record associated with the ticket.
    It will iterate over every MIME part and store all MIME parts as attachments apart
    from the text/plain part.
    There may be a case for trying to exclude repeated signature images by checking if an
    attachment of the same name already exists as an attachment on the ticket but that is
    not implemented.
    :param message: the raw email message received
    :param queue: the queue that the message is assigned to
    :param logger: the logger to be used
    '''
    # 'message' must be an RFC822 formatted message to correctly parse.
    # NBot sure why but policy explicitly set to default is required for any messages with attachments in them
    message_obj: EmailMessage = email.message_from_string(message, EmailMessage, policy=policy.default)

    subject = extract_email_subject(message_obj)

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
    files = []
    # first message in thread, we save full body to avoid losing forwards and things like that
    include_chained_msgs = True if ticket_id is None and getattr(
        django_settings, 'HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL', False) else False
    filtered_body, full_body = extract_email_message_content(message_obj, files, include_chained_msgs)
    # If the base part is not a multipart then it will have already been processed as the vbody content so
    # no need to process attachments
    if "multipart" == message_obj.get_content_maintype() and settings.HELPDESK_ENABLE_ATTACHMENTS:
        # Find and attach all other parts or part contents as attachments
        counter, content_parts_excluded = extract_attachments(message_obj, files, logger)
        if not content_parts_excluded:
            # Unexpected situation and may mean there is a hole in the email processing logic
            logger.warning(
                "Failed to exclude email content when parsing all MIME parts in the multipart.\
                 Verify that there were no text/* parts containing message content.")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Email parsed and %s attachments were found and attached.", counter)
    if settings.HELPDESK_ENABLE_ATTACHMENTS:
        add_file_if_always_save_incoming_email_message(files, message)

    smtp_priority = message_obj.get('priority', '')
    smtp_importance = message_obj.get('importance', '')
    high_priority_types = {'high', 'important', '1', 'urgent'}
    priority = 2 if high_priority_types & {
        smtp_priority, smtp_importance} else 3

    payload = {
        'body': filtered_body,
        'full_body': full_body,
        'subject': subject,
        'queue': queue,
        'sender_email': sender_email,
        'priority': priority,
        'files': files,
    }

    return create_object_from_email_message(message_obj, ticket_id, payload, files, logger=logger)
