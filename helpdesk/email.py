"""
Django Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. Copyright 2018 Timothy Hobbs. All Rights Reserved.
See LICENSE for details.
"""
from base64 import urlsafe_b64decode
from html import unescape
import email
import imaplib
import logging
import mimetypes
import os
import poplib
import re
import socket
import ssl
from datetime import timedelta, datetime
import dateutil
from email.utils import getaddresses, parseaddr
from os.path import isfile, join
from time import ctime
from functools import reduce
from buildingid.code import RE_PATTERN_
import quopri

from bs4 import BeautifulSoup
from bs4.builder import ParserRejectedMarkup
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.mail import BadHeaderError
from django.db.models import Q
from django.utils import encoding, timezone
from django.utils.translation import ugettext as _
from email_reply_parser import EmailReplyParser

from exchangelib import FileAttachment, ItemAttachment, Message as ExchangeMessage
from exchangelib.errors import ErrorInternalServerError

from helpdesk import settings
from helpdesk.lib import safe_template_context, process_attachments
from helpdesk.models import Ticket, TicketCC, FollowUp, IgnoreEmail, FormType, CustomField, is_extra_data
from seed.models import EmailImporter, GOOGLE, MICROSOFT, EXCHANGE_OAUTH, EXCHANGE_PASS
from helpdesk.decorators import is_helpdesk_staff
from post_office.models import Email


# import User model, which may be a custom model
User = get_user_model()


STRIPPED_SUBJECT_STRINGS = [
    "Re: ",
    "Fw: ",
    "RE: ",
    "FW: ",
    "Automatic reply: ",
    "[EXTERNAL] "  # NJ
]

PATTERN_UID = re.compile(r'\d+ \(UID (?P<uid>\d+)\)')
DEBUGGING = False
UBID_PATTERN = RE_PATTERN_.pattern[1:len(RE_PATTERN_.pattern) - 1]  # removes ^ and $
ADDR_PATTERN = re.compile('\s?\"(.*?)\" <([^<>,\s@]+@[^<>,\s@]+)>|\s?([^<>,]+) <([^<>,\s@]+@[^<>,\s@]+)>|([^<>,\s@]+@[^<>,\s@]+)')


def parse_uid(data):
    match = PATTERN_UID.match(data)
    return match.group('uid')


def process_email(quiet=False, debugging=False, options=None):
    for importer in EmailImporter.objects.filter(allow_email_imports=True):
        importer_queues = importer.queue_set.all()

        log_name = importer.email_address.replace('@', '_')
        log_name = log_name.replace('.', '_')
        logger = logging.getLogger(log_name)
        logging_types = {
            'info': logging.INFO,
            'warn': logging.WARN,
            'error': logging.ERROR,
            'crit': logging.CRITICAL,
            'debug': logging.DEBUG,
        }
        if importer.logging_type in logging_types:
            logger.setLevel(logging_types[importer.logging_type])
        elif not importer.logging_type or importer.logging_type == 'none':
            # disable all handlers so messages go to nowhere
            logger.handlers = []
            logger.propagate = False
        if quiet:
            logger.propagate = False  # do not propagate to root logger that would log to console

        # Log messages to specific file only if the queue has it configured
        if (importer.logging_type in logging_types) and importer.logging_dir:  # if it's enabled and the dir is set
            log_file_handler = logging.FileHandler(join(importer.logging_dir, log_name + '_get_email.log'))
            logger.addHandler(log_file_handler)
        else:
            log_file_handler = None

        try:
            if not importer.default_queue:
                logger.info("Import canceled: no default queue set")
            else:
                default_queue = importer.default_queue

                matching_queues = importer_queues.exclude(match_on__exact=[])
                address_matching_queues = importer_queues.exclude(match_on_addresses__exact=[])
                queues = {
                    'importer_queues': importer_queues,
                    'default_queue': default_queue,
                    'matching_queues': matching_queues,
                    'address_matching_queues': address_matching_queues
                }

                if not importer.email_box_last_check:
                    importer.email_box_last_check = timezone.now() - timedelta(minutes=30)

                queue_time_delta = timedelta(minutes=importer.email_box_interval or 0)
                if debugging or DEBUGGING:
                    process_importer(importer, queues, logger=logger, debugging=True, options=options)
                    importer.email_box_last_check = timezone.now()
                    importer.save()
                elif (importer.email_box_last_check + queue_time_delta) < timezone.now():
                    process_importer(importer, queues, logger=logger, debugging=False, options=options)
                    importer.email_box_last_check = timezone.now()
                    importer.save()
                else:
                    logger.info('Import canceled: Too early to check')

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


def process_importer(importer, queues, logger, debugging, options=None):
    logger.debug("***** %s: Begin processing mail for django-helpdesk" % ctime())

    if importer.socks_proxy_type and importer.socks_proxy_host and importer.socks_proxy_port:
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
        }.get(importer.socks_proxy_type)

        socks.set_default_proxy(proxy_type=proxy_type,
                                addr=importer.socks_proxy_host,
                                port=importer.socks_proxy_port)
        socket.socket = socks.socksocket

    email_box_type = settings.QUEUE_EMAIL_BOX_TYPE or importer.email_box_type

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
        if importer.email_box_ssl or settings.QUEUE_EMAIL_BOX_SSL:
            encryption = 'ssl'
        if not importer.email_box_port:
            importer.email_box_port = mail_defaults[email_box_type][encryption]['port']
        if email_box_type == 'imap':
            try:
                server = mail_defaults[email_box_type][encryption]['init'](
                    importer.email_box_host or settings.QUEUE_EMAIL_BOX_HOST,
                    int(importer.email_box_port),
                    timeout=60
                )
            except ConnectionResetError:
                logger.warn("Connection reset, unable to import")
                return
        else:
            server = mail_defaults[email_box_type][encryption]['init'](
                importer.email_box_host or settings.QUEUE_EMAIL_BOX_HOST,
                int(importer.email_box_port)
            )
        logger.info("Attempting %s server login" % email_box_type)
        mail_defaults[email_box_type]['sync'](importer, queues, logger, server, debugging=debugging, options=options)

    elif email_box_type == 'local':
        mail_dir = importer.email_box_local_dir or '/var/lib/mail/helpdesk/'
        mail = [join(mail_dir, f) for f in os.listdir(mail_dir) if isfile(join(mail_dir, f))]
        logger.info("Found %d messages in local mailbox directory" % len(mail))
        for i, m in enumerate(mail, 1):
            logger.info("Processing message %d" % i)
            with open(m, 'r') as f:
                full_message = encoding.force_text(f.read(), errors='replace')
                ticket = process_message(full_message, importer, queues, logger)
            if ticket:
                logger.info("Successfully processed message %d, ticket/comment created.", i)
                try:
                    os.unlink(m)  # delete message file if ticket was successful
                except OSError as e:
                    logger.error("Unable to delete message %d (%s).", i, str(e))
                else:
                    logger.info("Successfully deleted message %d.", i)
            else:
                logger.warn("Message %d was not successfully processed, and will be left in local directory", i)

    elif importer.auth:
        if importer.auth.host_service == EXCHANGE_OAUTH or importer.auth.host_service == EXCHANGE_PASS:
            logger.info("Attempting Exchange server login")
            server, _ = importer.auth.login(email=importer, logger=logger)
            if server:
                exchange_sync(importer, queues, logger, server, debugging=debugging)
        elif importer.auth.host_service == GOOGLE:
            logger.info("Attempting Google server login")
            server, _ = importer.auth.login(email=importer, logger=logger)
            if server:
                google_sync(importer, queues, logger, server, debugging=debugging, options=options)


def pop3_sync(importer, queues, logger, server, debugging):
    server.getwelcome()
    try:
        server.stls()
    except Exception:
        logger.warning("POP3 StartTLS failed or unsupported. Connection will be unencrypted.")
    server.user(importer.username or settings.QUEUE_EMAIL_BOX_USER)
    server.pass_(importer.password or settings.QUEUE_EMAIL_BOX_PASSWORD)

    messages_info = server.list()[1]
    logger.info("Received %s messages from POP3 server" % len(messages_info))

    for msg_raw in messages_info:
        if type(msg_raw) is bytes:
            try:
                msg = msg_raw.decode("utf-8")
            except UnicodeError:
                # if couldn't decode easily, just leave it raw
                msg = msg_raw
        else:
            # already a str
            msg = msg_raw
        msg_num = msg.split(" ")[0]
        logger.info("Processing message %s" % msg_num)

        raw_content = server.retr(msg_num)[1]
        if type(raw_content[0]) is bytes:
            full_message = "\n".join([elm.decode('utf-8') for elm in raw_content])
        else:
            full_message = encoding.force_text("\n".join(raw_content), errors='replace')
        ticket = process_message(full_message, importer, queues, logger)

        if ticket:
            if not debugging:
                server.dele(msg_num)
            logger.info("Successfully processed message %s, deleted from POP3 server\n" % msg_num)
        else:
            logger.warn("Message %s was not successfully processed, and will be left on POP3 server\n" % msg_num)

    server.quit()


def generate_oauth2_string(user, token):
    auth_string = f"user={user}\1auth=Bearer {token}\1\1"
    return auth_string


def refreshed(importer, logger, token_backend=None):
    # checks if token needs refreshing - if so, refreshes it
    if not token_backend:
        return False
    try:
        was_refreshed = token_backend.should_refresh_token(expr_minutes=1)
    except RuntimeError:
        logger.error(f"* Token could not be refreshed by refreshed(). Exiting import for {importer.email_address}.")
        return False

    if was_refreshed is None:
        logger.info(f"* Token was refreshed. Exiting import for {importer.email_address}.")
        return True  # The token was refreshed - stop now
    else:
        return False  # The token is still good - keep going


def imap_sync(importer, queues, logger, server, debugging, options=None):
    login_successful = True
    token_backend = None
    # server.debug = 4

    if importer.auth and (importer.auth.host_service == GOOGLE or importer.auth.host_service == MICROSOFT):
        # Start TLS first
        try:
            server.starttls()
        except Exception:
            logger.warning("IMAP4 StartTLS unsupported or failed. Connection will be unencrypted.")

        # Next, acquire the token
        token_backend = importer.auth.get_access_token_backend()
        try:
            token_backend.should_refresh_token()
        except RuntimeError:
            logger.error(f"* Token could not be refreshed by should_refresh_token. Exiting import for {importer.email_address}.")
            login_successful = False
        else:
            logger.info("* Authenticating and selecting box.")
            try:
                server.authenticate('XOAUTH2', lambda x: generate_oauth2_string(importer.username, token_backend.token['access_token']))
                server.select(importer.email_box_imap_folder)
            except Exception as e:
                logger.error(f"IMAP authentication failed: {e}")
                logger.error(f"Exiting import for {importer.email_address}.")
                login_successful = False
    else:
        try:
            server.starttls()
        except Exception:
            logger.warning("IMAP4 StartTLS unsupported or failed. Connection will be unencrypted.")
        try:
            server.login(importer.username or settings.QUEUE_EMAIL_BOX_USER,
                         importer.password or settings.QUEUE_EMAIL_BOX_PASSWORD)
            server.select(importer.email_box_imap_folder)
        except imaplib.IMAP4.abort:
            logger.error("IMAP login failed. Check that the server is accessible and that "
                         "the username and password are correct.")
            login_successful = False
        except ssl.SSLError:
            logger.error("IMAP login failed due to SSL error. This is often due to a timeout. "
                         "Please check your connection and try again.")
            login_successful = False
        except imaplib.IMAP4.error:
            try:
                logger.error("IMAP login failed. Trying again...")
                server.login(importer.username or settings.QUEUE_EMAIL_BOX_USER,
                             importer.password or settings.QUEUE_EMAIL_BOX_PASSWORD)
                server.select(importer.email_box_imap_folder)
            except Exception:
                logger.error("IMAP login failed.")
                login_successful = False
    # server.debug = 3

    if login_successful:
        try:
            if importer.keep_mail:
                status, data = server.search(None, 'NOT', 'ANSWERED')
            else:
                status, data = server.search(None, 'NOT', 'DELETED')

            if data:
                msg_nums = data[0].split()
                logger.debug("Received %s messages from IMAP server" % len(msg_nums))
                # check whether our token is running out of time - if so, or if we refreshed it, just stop here.
                # we don't want to get interrupted mid-import, and accidentally import twice!
                refreshed_flag = refreshed(importer, logger, token_backend)
                for num_raw in msg_nums:
                    if not refreshed_flag:
                        # Get UID and use that
                        resp, uid = server.fetch(num_raw, "(UID)")
                        if not uid:
                            logger.error("Could not fetch UID. Message will not be processed; skipping to the next message. num_raw: %s, resp: %s, uid: %s" % (num_raw, resp, uid))
                        else:
                            uid = uid[0].decode('ascii')
                            msg_uid = parse_uid(uid)
                            logger.debug("Received message UID: %s" % msg_uid)

                            # Grab message first to get date to sort by
                            status, data = server.uid('fetch', msg_uid, '(RFC822)')
                            full_message = encoding.force_text(data[0][1], errors='replace')
                            try:
                                ticket = process_message(full_message, importer, queues, logger, options=options)
                            except TypeError as e:
                                logger.error("Type error - ticket set to None")
                                logger.error(e)
                                logger.error('Error printed above.')
                                ticket = None  # hotfix. Need to work out WHY.
                            except BadHeaderError:
                                # Malformed email received from the server
                                logger.error("BadHeaderError - ticket set to None")
                                ticket = None
                            except Exception as e:
                                logger.error("Unknown exception - ticket set to None")
                                logger.error(e)
                                logger.error('Error printed above.')
                                ticket = None
                            if ticket:
                                if debugging:
                                    logger.info("Successfully processed message %s, left untouched on IMAP server\n" % msg_uid)
                                elif importer.keep_mail:
                                    # server.store(num, '+FLAGS', '\\Answered')
                                    ov, data = server.uid('STORE', msg_uid, '+FLAGS', '(\\Answered)')
                                    logger.info("Successfully processed message %s, marked as Answered on IMAP server\n" % msg_uid)
                                else:
                                    # server.store(num, '+FLAGS', '\\Deleted')
                                    ov, data = server.uid('STORE', msg_uid, '+FLAGS', '(\\Deleted)')
                                    logger.info("Successfully processed message %s, deleted from IMAP server\n" % msg_uid)
                            else:
                                logger.warn("Message %s was not successfully processed, and will be left on IMAP server\n" % msg_uid)
                        refreshed_flag = refreshed(importer, logger, token_backend)
        except imaplib.IMAP4.error:
            logger.error(
                "IMAP retrieve failed. Is the folder '%s' spelled correctly, and does it exist on the server?",
                importer.email_box_imap_folder
            )
        server.expunge()
        server.close()

        server.logout()


def exchange_sync(importer, queues, logger, server, debugging):
    # first, connect

    # select box from email_box_imap_folder
    folder = None
    if importer.email_box_imap_folder.lower() == 'inbox':
        folder = server.inbox
    else:
        folders = server.root.glob(importer.email_box_imap_folder)
        if len(folders) > 1:
            logger.error('Error - be more specific')  # todo
        elif len(folders) == 0:
            logger.error('Error - folder not found')  # todo
        else:
            folder = folders[0]

    # filter for mail
    if folder:
        if importer.keep_mail:
            data = folder.filter(is_read=False)
        else:
            data = folder.all()

        values = [
            '_id',  # id is an ItemID and change_key. These CAN change if the item is moved or updated
            'conversation_id',  # Exchange id type referring to conversation/thread, includes change_key
            'headers',
            'sender',  # email address that sent the mail for the author (?)
            'author',  # email address that created the mail
            'to_recipients', 'cc_recipients', 'bcc_recipients',  # lists of mailbox objects
            'subject', 'conversation_topic',  # subject and original subject ("Re: FW: Subject" vs "FW: Subject")
            'text_body', 'body', 'unique_body',  # Body with HTML
            'attachments', 'has_attachments',  # has_attachments does not include inline attachments
            'size',
            'message_id', 'in_reply_to',  # message-id of the message this is replying to, or None
            'references',  # string of message-ids involved in the thread, or None. ('<id1> <id2> <id3>')
            'is_from_me',
            'is_read',
            'importance',
        ]
        data = data.order_by('datetime_received').only(*values)

        try:
            # loop thru msgs
            msg_num = data.count()
            logger.debug("Received %s messages from IMAP server" % msg_num)
            for item in data:
                # item = data[0]
                msg_id = getattr(item, '_id', None)
                if not msg_id:
                    logger.error("Could not fetch UID. Message will not be processed; skipping to the next message.\nEmail info:\n%s" % item)
                else:
                    logger.debug("Received message ID: %s" % msg_id)
                    try:
                        ticket = process_exchange_message(item, importer, queues, logger)
                    except Exception as e:
                        logger.error('Unable to process message into ticket: ', str(e))  # todo
                        ticket = None
                    if ticket:
                        if debugging:
                            logger.info("Successfully processed message %s, left untouched on server\n" % msg_id.id)
                        else:
                            try:
                                item_obj = folder.get(id=msg_id.id, changekey=msg_id.changekey)
                            except Exception:
                                logger.error("Unable to retrieve message %s for final processing, left untouched on server." % msg_id.id)
                            else:
                                if importer.keep_mail:
                                    item_obj.is_read = True
                                    item_obj.save(update_fields=['is_read'])
                                    logger.info("Successfully processed message %s, marked as Answered on server\n" % msg_id.id)
                                else:
                                    item_obj = folder.get(id=msg_id.id, changekey=msg_id.changekey)
                                    item_obj.soft_delete()
                                    logger.info("Successfully processed message %s, deleted from server\n" % msg_id.id)
                    else:
                        logger.warn("Message %s was not successfully processed, and will be left on IMAP server\n" % msg_id.id)
        except Exception as e:
            logger.error(e)  # todo


def google_sync(importer, queues, logger, server, debugging, options=None):
    # first, connect

    # select box from email_box_imap_folder
    labels = ['INBOX']
    if importer.keep_mail:
        labels.append('UNREAD')
    if options and 'labels' in options:
        for label in options['labels']:
            labels.append(label)
    response = server.users().messages().list(userId='me', labelIds=labels).execute()
    if 'resultSizeEstimate' in response and response['resultSizeEstimate'] == 0:
        logger.info("Received 0 messages from server")
        return
    elif 'messages' not in response:
        logger.error(f'Received unexpected response: {response}')
        return
    msgs = response['messages']
    logger.debug("Received %s messages from server" % len(msgs))
    # ids_to_delete = []
    # filter for mail
    for item in msgs:
        try:
            # item is an id and thread id
            msg_id = item['id']
            msg = server.users().messages().get(userId='me', id=msg_id).execute()
            logger.debug("Received message ID: %s" % msg_id)
            try:
                ticket = process_google_message(msg['payload'], importer, queues, logger, msg_id, server)
            except Exception as e:
                logger.error('Unable to process message into ticket: ', str(e))  # todo
                ticket = None
            if ticket:
                if debugging:
                    logger.info("Successfully processed message %s, left untouched on server\n" % msg_id)
                else:
                    if importer.keep_mail:
                        server.users().messages().modify(userId='me', id=msg_id, body={'removeLabelIds': ['UNREAD']}).execute()
                        logger.info("Successfully processed message %s, marked as Read on server\n" % msg_id)
                    else:
                        try:
                            server.users().messages().trash(userId='me', id=msg_id).execute()
                        except Exception:
                            # try it again
                            server.users().messages().trash(userId='me', id=msg_id).execute()
                        # ids_to_delete.append(msg_id)
                        logger.info("Successfully processed message %s, deleted from server\n" % msg_id)
            else:
                logger.warn("Message %s was not successfully processed, and will be left on server\n" % msg_id)
        except Exception as e:
            logger.error(e)  # todo
            logger.warn("Message was not successfully processed, and will be left on server\n")
    # if ids_to_delete:
    #     server.users().messages().batch_delete(userId='me', ids=ids_to_delete).execute()
    #     logger.info('Deleted messages: %s' % ids_to_delete)


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
    return u' '.join([
        str(msg, encoding=charset, errors='replace') if charset else str(msg)
        for msg, charset
        in decoded
    ])


def is_autoreply(message, sender='', subject='', headers=None):
    """
    Accepting message as something with .get(header_name) method
    Returns True if it's likely to be auto-reply or False otherwise
    So we don't start mail loops
    """
    sender = sender.lower()
    subject = subject.lower()
    if headers:
        message = headers
    any_if_this = [
        False if not message.get("Auto-Submitted") else message.get("Auto-Submitted", '').lower() != "no",
        False if not message.get("auto-submitted") else message.get("auto-submitted", '').lower() != "no",
        True if message.get("x-auto-response-suppress", '').lower() in ("dr", "autoreply", "all") else False,
        True if message.get("X-Auto-Response-Suppress", '').lower() in ("dr", "autoreply", "all") else False,
        message.get("List-Id"),
        message.get("list-id"),
        message.get("List-Unsubscribe"),
        message.get("list-unsubscribe"),
        'no-reply' in sender,
        'noreply' in sender,
        'donotreply' in sender,
        'postmaster' in sender,
        'mailer-daemon' in sender,
        'out of office' in subject,
        'undelivered' in subject,
        'undeliverable' in subject,
        False if not message.get("Return-Path") else message.get("Return-Path", '').lower() == 'mailer-daemon',
        False if not message.get("return-path") else message.get("return-path", '').lower() == 'mailer-daemon',
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
        cced_email_lower = cced_email.lower()
        if cced_email_lower == ticket.queue.email_address.lower():
            continue
        if 'donotreply' in cced_email_lower or 'no-reply' in cced_email_lower or 'noreply' in cced_email_lower or 'postmaster' in cced_email_lower:  # todo make a global var for this
            continue
        if ticket.queue.organization.sender and cced_email_lower == ticket.queue.organization.sender.email_address.lower():  # todo also check importer?
            continue
        if cced_email == (ticket.submitter_email or '') or cced_email == (ticket.contact_email or ''):
            continue
        if cced_email == 'benchmarking@bpu.nj.gov':  # NJ
            continue

        user = None
        try:
            user = User.objects.get(email=cced_email)
        except User.DoesNotExist:
            pass

        try:
            ticket_cc = subscribe_to_ticket_updates(ticket=ticket, user=user, email=cced_email)
            if ticket_cc is not None:
                new_ticket_ccs.append(ticket_cc)
        except ValidationError:
            pass

    return new_ticket_ccs


def create_ticket_from_processed_message(message, ticket_id, payload, files, logger, options=None):

    ticket, previous_followup, new = None, None, False
    now = timezone.now()

    queue = payload['queue']
    sender_name = payload['sender'][0]
    sender_email = payload['sender'][1]
    org = queue.organization
    date = payload.get('date', now)
    related_emails = payload.get('related_emails', None)
    ubids = re.findall(UBID_PATTERN, payload['subject'] + ' ' + payload['body'])
    if ubids:
        ubids = set(['-'.join(s) for s in ubids])
        ubids = ', '.join(ubids)

    message_id = getattr(message, 'message_id', None) or parseaddr(getattr(message, 'Message-Id', None))[1]
    in_reply_to = getattr(message, 'in_reply_to', None) or parseaddr(getattr(message, 'In-Reply-To', None))[1]
    if not in_reply_to and 'in_reply_to' in payload and payload['in_reply_to']:
        in_reply_to = _parse_addr_string(payload['in_reply_to'])[0][1]

    if in_reply_to:
        try:
            queryset = FollowUp.objects.filter(message_id=in_reply_to).order_by('-date')
            if queryset.count() > 0:
                previous_followup = queryset.first()
                ticket = previous_followup.ticket
                logger.info('Found ticket based on in_reply_to: [%s-%s]' % (ticket.queue.slug, ticket.id))
        except FollowUp.DoesNotExist:
            logger.info('FollowUp DoesNotExist error.')
            pass  # play along. The header may be wrong

    if previous_followup is None and ticket_id is not None:
        try:
            ticket = Ticket.objects.get(id=ticket_id)  # TODO also add in organization id? or, just ticket form (which will be diff for each org)?
            logger.info('Ticket found from a ticket_id %s: [%s-%s]' % (ticket_id, ticket.queue.slug, ticket.id))
        except Ticket.DoesNotExist:
            ticket = None
        else:
            new = False
            logger.info('Ticket is not new')
            # Check if the ticket has been merged to another ticket
            if ticket.merged_to:
                logger.info("Ticket has been merged to %s" % ticket.merged_to.ticket)
                # Use the ticket in which it was merged to for next operations
                ticket = ticket.merged_to

    # New issue, create a new <Ticket> instance
    if ticket is None:
        if not settings.QUEUE_EMAIL_BOX_UPDATE_ONLY:
            ticket_form = FormType.objects.get_or_create(name=settings.HELPDESK_EMAIL_FORM_NAME, organization=org)[0]
            fields = CustomField.objects.filter(ticket_form=ticket_form.id).values_list('field_name', flat=True)

            ticket = Ticket.objects.create(
                title=payload['subject'][0:200],
                queue=queue,
                contact_name=sender_name[0:200] if 'contact_name' in fields else None,
                contact_email=sender_email[0:200] if 'contact_email' in fields else None,
                submitter_email=sender_email,
                created=now,
                description=payload['body'],
                priority=payload['priority'],
                ticket_form=ticket_form,
                assigned_to=queue.default_owner if queue.default_owner else None,
            )
            ticket.created = date

            if ubids:
                # if ubids were found in the body, look for a field with UBID in the title
                ubid_field = ticket_form.customfield_set.filter(label__icontains='UBID', data_type='varchar')
                if ubid_field.count() == 1:
                    logger.info("Found UBIDs, adding them to the ticket.")
                    ubid_field = ubid_field.first()
                    if is_extra_data(ubid_field.field_name):
                        ticket.extra_data[ubid_field.field_name] = ubids
                    else:
                        setattr(ticket, ubid_field.field_name, ubids[0:200])  # the building_id field tends to be capped at 200 characters

            if related_emails:
                related_emails_field = ticket_form.customfield_set.filter(field_name='related_email', data_type='email')
                if related_emails_field.count() == 1:
                    logger.info("Found related emails, adding them to the ticket.")
                    related_emails_field = related_emails_field.first()
                    if is_extra_data(related_emails_field.field_name):
                        ticket.extra_data[related_emails_field.field_name] = related_emails

            ticket.save()
            logger.info("Created new ticket %s-%s" % (ticket.queue.slug, ticket.id))
            new = True

    f = FollowUp.objects.create(
        ticket=ticket,
        title=_('E-Mail Received from %(sender_email)s' % {'sender_email': sender_email})[0:200],
        date=date,
        public=True,
        comment=payload.get('full_body', payload['body']) or "",
        message_id=message_id
    )
    # Update ticket and follow-up status
    if not new:
        updater = User.objects.filter(email=sender_email).first()
        submitter = User.objects.filter(email=ticket.submitter_email).first()
        updater_is_staff = is_helpdesk_staff(updater, ticket.ticket_form.organization.id)
        submitter_is_staff = is_helpdesk_staff(submitter, ticket.ticket_form.organization.id)
        if (submitter_is_staff and updater is not ticket.assigned_to) or not updater_is_staff:
            # update is from a public user OR ticket's submitter is a staff member (ticket is internal)
            #   is ticket closed? -> Reopened
            #   else -> Open
            if ticket.status == Ticket.CLOSED_STATUS or ticket.status == Ticket.RESOLVED_STATUS or ticket.status == Ticket.DUPLICATE_STATUS:
                ticket.status = Ticket.REOPENED_STATUS
                f.new_status = Ticket.REOPENED_STATUS
                if updater_is_staff:
                    f.title = _('Ticket Re-Opened by E-Mail Received from %(user)s' % {'user': updater.get_full_name() or updater.get_username()})
                else:
                    f.title = _('Ticket Re-Opened by E-Mail Received from %(sender_email)s' % {'sender_email': sender_email})
            elif ticket.status == Ticket.REPLIED_STATUS:
                ticket.status = Ticket.OPEN_STATUS
                f.new_status = Ticket.OPEN_STATUS
        else:
            # reply is from staff and submitter is not staff -> Replied
            if ticket.status != Ticket.CLOSED_STATUS and ticket.status != Ticket.RESOLVED_STATUS and ticket.status != Ticket.DUPLICATE_STATUS:
                ticket.status = Ticket.REPLIED_STATUS
                f.new_status = Ticket.REPLIED_STATUS
        ticket.save()
        f.save()

    logger.info("Created new FollowUp for Ticket")
    logger.info("[%s-%s] %s" % (ticket.queue.slug, ticket.id, ticket.title,))

    attached = process_attachments(f, files)
    for att_file in attached:
        logger.info(
            "Attachment '%s' successfully added to ticket from email.",
            att_file[0]
        )

    context = safe_template_context(ticket)
    context['private'] = False

    headers = payload['headers'] if 'headers' in payload else None
    autoreply = is_autoreply(message, sender=sender_email, subject=payload['subject'], headers=headers)
    if autoreply:
        logger.info("Message seems to be auto-reply, not sending any emails back to the sender")
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
            new_ticket_ccs = create_ticket_cc(ticket, payload['to_list'] + payload['cc_list'])
            roles = {'submitter': ('newticket_submitter', context),
                     'queue_new': ('newticket_cc_user', context),
                     'queue_updated': ('newticket_cc_user', context),
                     'cc_users': ('newticket_cc_user', context),
                     'cc_public': ('newticket_cc_public', context),
                     'extra': ('newticket_cc_public', context)}
            if ticket.assigned_to:
                roles['assigned_to'] = ('assigned_owner', context)
            ticket.send_ticket_mail(roles, organization=org, fail_silently=True, extra_headers=extra_headers, email_logger=logger,
                                    source="import (new ticket)")
        else:
            new_ticket_ccs = create_ticket_cc(ticket, [(sender_name, sender_email)] + payload['to_list'] + payload['cc_list'])
            context.update(comment=f.comment)

            roles = {'submitter': ('updated_submitter', context),
                     'assigned_to': ('updated_owner', context),
                     'cc_users': ('updated_cc_user', context),
                     'queue_updated': ('updated_cc_user', context)}
            if queue.enable_notifications_on_email_events:
                roles['cc_public'] = ('updated_cc_public', context)
                roles['extra'] = ('updated_cc_public', context)

            ticket.send_ticket_mail(
                roles,
                organization=org,
                fail_silently=True,
                extra_headers=extra_headers,
                email_logger=logger,
                source="import"
            )
    return ticket

def process_message(message, importer, queues, logger, options=None):
    # 'message' must be an RFC822 formatted message.
    message = email.message_from_string(message)
    sender, to_list, cc_list, date, subject, category = None, [], [], None, None, None

    if importer.extract_eml_attachments:  # todo make a migration to check this off
        # for processing forwarded mail
        for part in message.walk():
            if part.get_content_maintype() == 'message':
                logger.info('Found .eml part. Extracting information now.')
                for eml_part in part.walk():
                    keys = eml_part.keys()
                    if 'from' in keys or 'To' in keys or 'Cc' in keys:
                        try:
                            if not parseaddr(eml_part.get('from', None)) == ('', ''):
                                sender = sender or parseaddr(eml_part.get('from', None))
                            to_list = to_list or getaddresses(eml_part.get_all('To', []))
                            cc_list = cc_list or getaddresses(eml_part.get_all('Cc', []))
                            if eml_part.get('date', None):
                                date = date or dateutil.parser.parse(eml_part.get('date'))
                            if eml_part.get('subject', None):
                                subject = subject or eml_part.get('subject')
                        except Exception:
                            pass
                break

    # Replaces original helpdesk code "get_charset()", which wasn't an actual method ?
    charset = list(filter(lambda s: s is not None, message.get_charsets()))
    if charset:
        charset = charset[0]

    if not subject:
        subject = message.get('subject', _('Comment from e-mail'))
    subject = decode_mail_headers(decode_unknown(charset, subject))
    for affix in STRIPPED_SUBJECT_STRINGS:
        subject = subject.replace(affix, "")
    subject = subject.strip()

    if not sender:
        sender = parseaddr(message.get('from', None))
    if sender[1] == '':
        # Delete emails if the sender email cannot be parsed correctly. This ensures that
        # mailing list emails do not become tickets as well as malformatted emails
        return True
    sender_lower = sender[1].lower()

    if not to_list:
        to_list = [x.replace('\r', '').replace('\n', '') for x in message.get_all('To', []) if x]
        to_list = getaddresses(to_list)
    if not cc_list:
        cc_list = [x.replace('\r', '').replace('\n', '') for x in message.get_all('Cc', []) if x]
        cc_list = getaddresses(cc_list)

    # Debugging issues with address resolution
    for (name, address) in to_list:
        if not address or '@' not in address:
            logger.error(f'ERROR: Bad to list.\nmessage.get_all: {message.get_all("To", [])}\nto_list: {to_list}')
            continue
    for (name, address) in cc_list:
        if not address or '@' not in address:
            logger.error(f'ERROR: Bad CC list.\nmessage.get_all: {message.get_all("Cc", [])}\ncc_list: {cc_list}')
            continue

    # preventing errors
    to_list = [(name, address) for name, address in to_list if '@' in address]
    cc_list = [(name, address) for name, address in cc_list if '@' in address]

    # Sort out which queue this email should go into #
    ticket, queue = None, None
    for q in queues['importer_queues']:
        matchobj = re.match(r".*\[" + q.slug + r"-(?P<id>\d+)\]", subject)
        if matchobj and not ticket:
            ticket = matchobj.group('id')
            queue = q
            logger.info("- Matched tracking ID %s-%s" % (q.slug, ticket))
    if not ticket:
        logger.info("- No tracking ID matched.")
        for q in queues['matching_queues']:
            if not queue:
                for m in q.match_on:
                    m_re = re.compile(r'\b%s\b' % m, re.I)
                    if m_re.search(subject):
                        queue = q
                        logger.info("- Subject matched list from '%s'" % q.slug)
    if not queue:
        for q in queues['address_matching_queues']:
            if reduce(lambda prev, e: prev or (e.lower() in sender_lower), q.match_on_addresses, False):
                queue = q
                logger.info("- Sender address matched list from '%s'" % q.slug)
    if not queue:
        logger.info("- Using default queue.")
        queue = queues['default_queue']

    # Ignore List applies to sender, TO emails, and CC list
    for ignored_address in IgnoreEmail.objects.filter(Q(queues=queue) | Q(organization=queue.organization, queues__isnull=True), ignore_import=True):
        if ignored_address.test(sender[1]):
            logger.info("Email address matched an ignored address. Ticket will not be created")
            if ignored_address.keep_in_mailbox:
                return False  # By returning 'False' the message will be kept in the mailbox,
            return True  # and the 'True' will cause the message to be deleted.

    # Accounting for forwarding loops
    auto_forward = message.get('X-BEAMHelpdesk-Delivered', None)
    if auto_forward is not None or (queue.email_address and sender_lower == queue.email_address.lower()):
        logger.info("Found a forwarding loop.")
        if ticket and Ticket.objects.filter(pk=ticket).exists():
            if sender_lower == queue.email_address.lower() and auto_forward is None:
                auto_forward = [i[1] for i in to_list]
            else:
                auto_forward = auto_forward.strip().split(',')
            for address in auto_forward:
                cc = TicketCC.objects.filter(ticket_id=ticket, email__iexact=address)
                if cc:
                    cc.delete()
                    logger.info("Deleted the CC'd address from the ticket")
                    logger.info("Address deleted was %s" % address)  # TODO remove later for privacy
        return True

    if 'date' in options and message.get('date', None):
        date = dateutil.parser.parse(message.get('date'))

    body = ''
    full_body = ''
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
                body = decode_unknown(part.get_content_charset(), body)
                # have to use django_settings here so overwritting it works in tests
                # the default value is False anyway
                if ticket is None:
                    # first message in thread, we save full body to avoid losing forwards and things like that
                    body_parts = []
                    for f in EmailReplyParser.read(body).fragments:
                        body_parts.append(f.content)
                    full_body = full_body + '\n'.join(body_parts)
                    body = EmailReplyParser.parse_reply(body)
                else:
                    # second and other reply, save only first part of the message
                    body = EmailReplyParser.parse_reply(body)
                    full_body = body
                # workaround to get unicode text out rather than escaped text
                try:
                    body = body.encode('ascii').decode('unicode_escape')
                except UnicodeEncodeError:
                    body = body.encode('utf-8').decode('unicode_escape')
                except UnicodeDecodeError:
                    pass
                logger.info("Discovered plain text MIME part")
            else:
                try:
                    email_body = encoding.smart_text(part.get_payload(decode=True))
                except UnicodeDecodeError:
                    email_body = encoding.smart_text(part.get_payload(decode=False))

                if not body and not full_body:
                    # no text has been parsed so far - try such deep parsing for some messages
                    altered_body = email_body.replace("</p>", "</p>\n").replace("<br", "\n<br")
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
                    SimpleUploadedFile(_("email_html_body.html"), payload.encode("utf-8"), 'text/html')
                )
                logger.info("Discovered HTML MIME part")
        else:
            if not name:
                ext = mimetypes.guess_extension(part.get_content_type())
                name = "part-%i%s" % (counter, ext)
            else:
                name = ("part-%i_" % counter) + name

            # # FIXME: this code gets the payloads, then does something with it and then completely ignores it
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
            files.append(SimpleUploadedFile(name, part.get_payload(decode=True), mimetypes.guess_type(name)[0]))
            logger.info("Found MIME attachment %s" % name)

        counter += 1

    if not body:
        try:
            mail = BeautifulSoup(str(message), "html.parser")
        except ParserRejectedMarkup:
            decoded_message = quopri.decodestring(str(message))
            mail = BeautifulSoup(decoded_message, "html.parser")

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
        # save message as attachment in case of some complex markup renders wrong
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
    priority = 2 if high_priority_types & {smtp_priority, smtp_importance} else 3

    payload = {
        'body': body,
        'full_body': full_body or body,
        'subject': subject,
        'queue': queue,
        'sender': sender,
        'priority': priority,
        'files': files,
        'cc_list': cc_list,
        'to_list': to_list,
    }
    if date:
        payload['date'] = date
    return create_ticket_from_processed_message(message, ticket, payload, files, logger=logger, options=options)

def process_exchange_message(message, importer, queues, logger):
    subject = message.subject
    if subject:
        for affix in STRIPPED_SUBJECT_STRINGS:
            subject = subject.replace(affix, "")
        subject = subject.strip()
    else:
        subject = ''

    if getattr(message, 'author', None):
        sender = (message.author.name, message.author.email_address)
    elif getattr(message, 'sender', None):
        sender = (message.sender.name, message.sender.email_address)
    else:
        sender = ('', '')
    sender_lower = sender[1].lower()

    to_list = []
    cc_list = []
    if getattr(message, 'to_recipients', None):
        to_list = [(r.name, r.email_address) for r in message.to_recipients]
    if getattr(message, 'cc_recipients', None):
        cc_list = [(r.name, r.email_address) for r in message.cc_recipients]

    # Debugging issues with address resolution
    for (name, address) in to_list:
        if not address or '@' not in address:
            logger.error(f'Bad to list.\nto_recipients: {message.to_recipients}\nto_list: {to_list}')
    for (name, address) in cc_list:
        if not address or '@' not in address:
            logger.error(f'Bad CC list.\ncc_recipients: {message.cc_recipients}\ncc_list: {cc_list}')

    # Sort out which queue this email should go into #
    ticket, queue = None, None
    for q in queues['importer_queues']:
        matchobj = re.match(r".*\[" + q.slug + r"-(?P<id>\d+)\]", subject)
        if matchobj and not ticket:
            ticket = matchobj.group('id')
            queue = q
            logger.info("- Matched tracking ID %s-%s" % (q.slug, ticket))
    if not ticket:
        logger.info("- No tracking ID matched.")
        for q in queues['matching_queues']:
            if not queue:
                for m in q.match_on:
                    m_re = re.compile(r'\b%s\b' % m, re.I)
                    if m_re.search(subject):
                        queue = q
                        logger.info("- Subject matched list from '%s'" % q.slug)
    if not queue:
        for q in queues['address_matching_queues']:
            if reduce(lambda prev, e: prev or (e.lower() in sender_lower), q.match_on_addresses, False):
                queue = q
                logger.info("- Sender address matched list from '%s'" % q.slug)
    if not queue:
        logger.info("- Using default queue.")
        queue = queues['default_queue']

    # Ignore List applies to sender, TO emails, and CC list
    for ignored_address in IgnoreEmail.objects.filter(Q(queues=queue) | Q(organization=queue.organization, queues__isnull=True), ignore_import=True):
        if ignored_address.test(sender[1]):
            logger.info("Email address matched an ignored address. Ticket will not be created")
            if ignored_address.keep_in_mailbox:
                return False  # By returning 'False' the message will be kept in the mailbox,
            return True  # and the 'True' will cause the message to be deleted.

    # Accounting for forwarding loops
    if getattr(message, 'headers'):
        headers = {h.name.lower(): h.value for h in getattr(message, 'headers', {})}
    else:  # catch for when getattr returns None
        headers = {}
    auto_forward = headers.get('x-beamhelpdesk-delivered', None)

    if auto_forward is not None or (queue.email_address and sender_lower == queue.email_address.lower()):
        logger.info("Found a forwarding loop.")
        if ticket and Ticket.objects.filter(pk=ticket).exists():
            if sender_lower == queue.email_address.lower() and auto_forward is None:
                auto_forward = [i[1] for i in to_list]
            else:
                auto_forward = auto_forward.strip().split(',')
            for address in auto_forward:
                cc = TicketCC.objects.filter(ticket_id=ticket, email__iexact=address)
                if cc:
                    cc.delete()
                    logger.info("Deleted the CC'd address from the ticket")
                    logger.info("Address deleted was %s" % address)  # TODO remove later for privacy
        return True

    files = []
    plain_body = getattr(message, 'text_body', '')
    html_body = getattr(message, 'body', '')
    unique_body = getattr(message, 'unique_body', '')
    full_text_body = ''
    latest_text_body = ''

    # 1. If there's a unique body, and the unique body isn't the same as the body (both are in html), use that.
    # Need both the latest_body and full_body. latest_body will be in the ticket comment and should be in plain text.
    # If latest_body: don't parse out the rest of it, just use all of it (for better or worse).
    # If not latest body: try parsing out the rest

    if unique_body and html_body != unique_body:
        logger.info('Found unique body.')
        altered_body = unique_body.replace("</p>", "</p>\n").replace("<br", "\n<br")
        mail = BeautifulSoup(str(altered_body), "html.parser")
        unique_body = str(mail)
        latest_text_body = EmailReplyParser.parse_reply(mail.get_text())

    if plain_body:
        logger.info('Found plain body.')
        body_parts = []
        for f in EmailReplyParser.read(plain_body).fragments:
            body_parts.append(f.content)
        plain_body = '\n\n'.join(body_parts)
        plain_body = re.sub('<mailto:[^>]*>', '', plain_body)
        plain_body = re.sub(r'^\[cid:[^]]*]$', '', plain_body, flags=re.MULTILINE)
        full_text_body = plain_body

        if not latest_text_body:
            latest_text_body = EmailReplyParser.parse_reply(full_text_body)

    if html_body:
        logger.info('Found HTML body.')
        html_body = html_body.replace('\n', '').replace('\r', '')
        altered_body = html_body.replace("</p>", "</p>\n").replace("<br>", "\n<br>").replace("<br/>", "\n<br/>")
        mail = BeautifulSoup(str(altered_body), "html.parser")
        html_body = str(mail)  # cids replaced with image tags
        if not full_text_body:
            full_text_body = mail.get_text()  # cids already removed
        if not latest_text_body:
            latest_text_body = EmailReplyParser.parse_reply(full_text_body)

        email_body = html_body
    elif plain_body:
        email_body = plain_body.replace('\n', '<br/>')
    else:
        email_body = unique_body

    # Next, save the entire email body
    logger.info('Saving email body as a file.')
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
        SimpleUploadedFile(_("email_html_body.html"), payload.encode("utf-8"), 'text/html')
    )

    logger.info("Found %s attachments." % len(message.attachments))
    att_counter = 0
    for attachment in message.attachments:
        if isinstance(attachment, FileAttachment):
            file_content = []
            logger.info('- Found FileAttachment')
            name = getattr(attachment, 'name', None)
            file_type = getattr(attachment, 'content_type', None)
            with attachment.fp as fp:
                buffer = fp.read(1024)
                while buffer:
                    file_content.append(buffer)
                    buffer = fp.read(1024)
            file_content = b''.join(file_content)
            files.append(SimpleUploadedFile(name, file_content, file_type))

        elif isinstance(attachment, ItemAttachment):
            logger.info('- Found ItemAttachment')
            if isinstance(attachment.item, ExchangeMessage):
                att_sender, att_to_list = '', []
                att_subject = getattr(attachment.item, 'subject', '')
                if getattr(attachment.item, 'sender', None):
                    att_sender = (attachment.item.sender.name, attachment.item.sender.email_address)
                if getattr(attachment.item, 'to_recipients', None):
                    att_to_list = [(r.name, r.email_address) for r in attachment.item.to_recipients]
                att_html_body = attachment.item.body.replace('\n', '').replace('\r', '').replace("</p>", "</p>\n").replace("<br>", "\n<br>").replace("<br/>", "\n<br/>")
                att_html_body = f"<p>Subject:{att_subject}<br>\nFrom: {att_sender}<br>\nTo: {att_to_list}</p>\n" + att_html_body
                att_html_body = str(BeautifulSoup(str(att_html_body), "html.parser"))
                files.append(SimpleUploadedFile(("email_html_attachment_%s.html" % att_counter), att_html_body.encode("utf-8"), 'text/html'))
                att_counter += 1

                # Check for more attachments
                for sub_attachment in attachment.item.attachments:
                    if isinstance(sub_attachment, FileAttachment):
                        logger.info('- Found Sub FileAttachment')
                        file_content = []
                        name = getattr(sub_attachment, 'name', None)
                        file_type = getattr(sub_attachment, 'content_type', None)
                        with sub_attachment.fp as fp:
                            buffer = fp.read(1024)
                            while buffer:
                                file_content.append(buffer)
                                buffer = fp.read(1024)
                        file_content = b''.join(file_content)
                        files.append(SimpleUploadedFile(name, file_content, file_type))

                    elif isinstance(sub_attachment, ItemAttachment):
                        logger.info('- Found Sub ItemAttachment')
                        try:
                            hasattr(sub_attachment, 'item')
                        except ErrorInternalServerError:
                            logger.info('- Sub ItemAttachment had no item, skipping')
                        else:
                            if isinstance(sub_attachment.item, ExchangeMessage):
                                att_sender, att_to_list, att_html_body = '', [], ''
                                att_subject = getattr(sub_attachment.item, 'subject', '')
                                if getattr(sub_attachment.item, 'sender', None):
                                    att_sender = (sub_attachment.item.sender.name, sub_attachment.item.sender.email_address)
                                if getattr(sub_attachment.item, 'to_recipients', None):
                                    att_to_list = [(r.name, r.email_address) for r in sub_attachment.item.to_recipients]
                                if getattr(sub_attachment.item, 'body', None):
                                    att_html_body = sub_attachment.item.body.replace('\n', '').replace('\r', '').replace("</p>", "</p>\n").replace("<br>", "\n<br>").replace("<br/>", "\n<br/>")
                                    att_html_body = f"<p>Subject:{att_subject}<br>\nFrom: {att_sender}<br>\nTo: {att_to_list}</p>\n" + att_html_body
                                    att_html_body = str(BeautifulSoup(str(att_html_body), "html.parser"))
                                files.append(SimpleUploadedFile(("email_html_subattachment_%s.html" % att_counter), att_html_body.encode("utf-8"), 'text/html'))
                                att_counter += 1

    smtp_importance = getattr(message, 'importance', '')
    high_priority_types = {'high', 'important', '1', 'urgent'}
    priority = 2 if high_priority_types & {smtp_importance} else 3
    payload = {
        'body': full_text_body or latest_text_body,  # the actual entire body
        'full_body': latest_text_body or full_text_body,  # just the latest body
        'subject': subject,
        'queue': queue,
        'sender': sender,
        'priority': priority,
        'files': files,
        'cc_list': cc_list,
        'to_list': to_list,
        'headers': headers
    }
    return create_ticket_from_processed_message(message, ticket, payload, files, logger=logger)

def _parse_addr_string(addresses):
    # Takes a string of one or more addresses from a message,
    # and returns a list of tuples [(name, address)]
    #
    # ex: a@a.com, "Name" <a@a.com>, "Last, First" <b@a.com>, Unquoted Name <c@c.com>
    # -> [('', 'a@a.com'), ('Name', 'a@a.com'), ('Last, First', 'b@a.com'), ('Unquoted Name', 'c@c.com')]
    address_groups = ADDR_PATTERN.findall(addresses)
    addr_list = []
    for a in address_groups:
        if a[0]:
            addr_list.append((a[0], a[1]))
        elif a[2]:
            addr_list.append((a[2], a[3]))
        elif a[4]:
            addr_list.append(('', a[4]))
    return addr_list

def process_google_message(message, importer, queues, logger, msg_id, server):
    headers = message['headers']
    sender, to_list, cc_list, date, subject, category, message_id, in_reply_to = '', [], [], None, '', None, None, None
    auto_forward = None

    if importer.extract_eml_attachments:
        pass # todo

    # Get subject, sender, to_list, cc_list
    for header in headers:
        header_name = header['name'].lower()
        if header_name == 'subject':
            subject = header['value']
            for affix in STRIPPED_SUBJECT_STRINGS:
                subject = subject.replace(affix, "")
            subject = subject.strip()
        elif header_name == 'from':
            sender = _parse_addr_string(header['value'])
            sender = sender[0] if sender else ''
        elif header_name == 'to':
            to_list = _parse_addr_string(header['value'])
        elif header_name == 'x-beamhelpdesk-delivered':
            auto_forward = header['value']
        elif header_name == 'cc':
            cc_list = _parse_addr_string(header['value'])
        elif header_name == 'message-id':
            message_id = header['value']
        elif header_name == 'in-reply-to':
            in_reply_to = header['value']
    sender_lower = sender[1].lower()
    # Use subject & to_list/cc_list to determine queue

    # Sort out which queue this email should go into #
    ticket, queue = None, None
    for q in queues['importer_queues']:
        matchobj = re.match(r".*\[" + q.slug + r"-(?P<id>\d+)\]", subject)
        if matchobj and not ticket:
            ticket = matchobj.group('id')
            queue = q
            logger.info("- Matched tracking ID %s-%s" % (q.slug, ticket))
    if not ticket:
        logger.info("- No tracking ID matched.")
        for q in queues['matching_queues']:
            if not queue:
                for m in q.match_on:
                    m_re = re.compile(r'\b%s\b' % m, re.I)
                    if m_re.search(subject):
                        queue = q
                        logger.info("- Subject matched list from '%s'" % q.slug)
    if not queue:
        for q in queues['address_matching_queues']:
            if reduce(lambda prev, e: prev or (e.lower() in sender_lower), q.match_on_addresses, False):
                queue = q
                logger.info("- Sender address matched list from '%s'" % q.slug)
    if not queue:
        logger.info("- Using default queue.")
        queue = queues['default_queue']

    # Ignore List applies to sender, TO emails, and CC list
    for ignored_address in IgnoreEmail.objects.filter(Q(queues=queue) | Q(organization=queue.organization, queues__isnull=True), ignore_import=True):
        if ignored_address.test(sender[1]):
            logger.info("Email address matched an ignored address. Ticket will not be created")
            if ignored_address.keep_in_mailbox:
                return False  # By returning 'False' the message will be kept in the mailbox,
            return True  # and the 'True' will cause the message to be deleted.

    # Accounting for forwarding loops
    if auto_forward is not None or (queue.email_address and sender_lower == queue.email_address.lower()):
        logger.info("Found a forwarding loop.")
        if ticket and Ticket.objects.filter(pk=ticket).exists():
            if sender_lower == queue.email_address.lower() and auto_forward is None:
                auto_forward = [i[1] for i in to_list]
            else:
                auto_forward = auto_forward.strip().split(',')
            for address in auto_forward:
                cc = TicketCC.objects.filter(ticket_id=ticket, email__iexact=address)
                if cc:
                    cc.delete()
                    logger.info("Deleted the CC'd address from the ticket")
                    logger.info("Address deleted was %s" % address)  # TODO remove later for privacy
        return True

    body = ''
    full_body = ''
    counter = 0
    files = []
    related_emails = set()

    def walk(parts_list):
        # function for recursively walking through parts of message
        nonlocal body, full_body, counter, files, related_emails
        for part in parts_list:
            filename = None
            if 'filename' in part and part['filename']:
                filename = part['filename']

            if 'text' in part['mimeType'] and filename is None:
                data = part['body']['data']
                if part['mimeType'] == 'text/plain':
                    body = urlsafe_b64decode(data).decode('utf-8')
                    if ticket is None:
                        # first message in thread, we save full body to avoid losing forwards and things like that
                        body_parts = []
                        for f in EmailReplyParser.read(body).fragments:
                            body_parts.append(f.content)
                        full_body = full_body + '\n'.join(body_parts)
                        body = EmailReplyParser.parse_reply(body)
                    else:
                        # second and other reply, save only first part of the message
                        body = EmailReplyParser.parse_reply(body)
                        full_body = body
                    logger.info("Discovered plain text MIME part")

                elif part['mimeType'] == 'text/html' and filename is None:
                    email_body = unescape(urlsafe_b64decode(data).decode('utf-8'))

                    if not body and not full_body:
                        # no text has been parsed so far - try such deep parsing for some messages
                        altered_body = email_body.replace("</p>", "</p>\n").replace("<br", "\n<br")
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
                        SimpleUploadedFile(_("email_html_body.html"), payload.encode("utf-8"), 'text/html')
                    )
                    logger.info("Discovered HTML MIME part")

            else:
                if 'attachmentId' in part['body']:
                    if not filename:
                        ext = mimetypes.guess_extension(part['mimeType'])
                        filename = "part-%i%s" % (counter, ext)
                    else:
                        filename = ("part-%i_" % counter) + filename
                    # todo write error catching
                    attachment = server.users().messages().attachments().get(userId='me', messageId=msg_id, id=part['body']['attachmentId']).execute()

                    data = urlsafe_b64decode(attachment['data'])
                    files.append(SimpleUploadedFile(filename, data, mimetypes.guess_type(filename)[0]))
                    counter = counter + 1
                    logger.info("Found MIME attachment %s" % filename)

            if 'parts' in part:
                walk(part['parts'])

            if 'headers' in part:
                for header in part['headers']:
                    if header['name'] == 'To':
                        related_emails.update(_parse_addr_string(header['value']))

    walk([message])
    if related_emails:
        related_emails = set(e[1] for e in related_emails)
        related_emails.discard(queue.email_address)
        related_emails = list(related_emails)

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
        # save message as attachment in case of some complex markup renders wrong
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

    payload = {
        'body': body,
        'full_body': full_body or body,
        'subject': subject,
        'queue': queue,
        'sender': sender,
        'priority': 3,  # todo
        'files': files,
        'cc_list': cc_list,
        'to_list': to_list,
        'message_id': message_id,
        'in_reply_to': in_reply_to,
        'related_emails': list(set(related_emails))
    }

    return create_ticket_from_processed_message(message, ticket, payload, files, logger=logger)#, nj=nj)