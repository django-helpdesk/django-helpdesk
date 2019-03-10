# -*- coding: utf-8 -*-
from django.test import TestCase
from django.core.management import call_command
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password

from helpdesk.models import Queue, Ticket, TicketCC, FollowUp, FollowUpAttachment
import helpdesk.email

import itertools
from shutil import rmtree
import sys
import os
from tempfile import mkdtemp
import logging


from urllib.parse import urlparse

from unittest import mock


THIS_DIR = os.path.dirname(os.path.abspath(__file__))

# class A addresses can't have first octet of 0
unrouted_socks_server = "0.0.0.1"
unrouted_email_server = "0.0.0.1"
# the last user port, reserved by IANA
unused_port = "49151"


class GetEmailCommonTests(TestCase):

    def setUp(self):
        self.queue_public = Queue.objects.create()
        self.logger = logging.getLogger('helpdesk')

    # tests correct syntax for command line option
    def test_get_email_quiet_option(self):
        """Test quiet option is properly propagated"""
        with mock.patch('helpdesk.management.commands.get_email.process_email') as mocked_processemail:
            call_command('get_email', quiet=True)
            mocked_processemail.assert_called_with(quiet=True)
            call_command('get_email')
            mocked_processemail.assert_called_with(quiet=False)

    def test_email_with_blank_body_and_attachment(self):
        """
        Tests that emails with blank bodies and attachments work.
        https://github.com/django-helpdesk/django-helpdesk/issues/700
        """
        with open(os.path.join(THIS_DIR, "test_files/blank-body-with-attachment.eml")) as fd:
            test_email = fd.read()
        ticket = helpdesk.email.object_from_message(test_email, self.queue_public, self.logger)
        self.assertEqual(ticket.title, "FollowUpAttachment without body")
        self.assertEqual(ticket.description, "")

    def test_email_with_quoted_printable_body(self):
        """
        Tests that emails with quoted-printable bodies work.
        """
        with open(os.path.join(THIS_DIR, "test_files/quoted_printable.eml")) as fd:
            test_email = fd.read()
        ticket = helpdesk.email.object_from_message(test_email, self.queue_public, self.logger)
        self.assertEqual(ticket.title, "Český test")
        self.assertEqual(ticket.description, "Tohle je test českých písmen odeslaných z gmailu.")
        followups = FollowUp.objects.filter(ticket=ticket)
        self.assertEqual(len(followups), 1)
        followup = followups[0]
        attachments = FollowUpAttachment.objects.filter(followup=followup)
        self.assertEqual(len(attachments), 1)
        attachment = attachments[0]
        self.assertEqual(attachment.file.read().decode("utf-8"), '<div dir="ltr">Tohle je test českých písmen odeslaných z gmailu.</div>\n')

    def test_email_with_8bit_encoding_and_utf_8(self):
        """
        Tests that emails with 8bit transfer encoding and utf-8 charset
        https://github.com/django-helpdesk/django-helpdesk/issues/732
        """
        with open(os.path.join(THIS_DIR, "test_files/all-special-chars.eml")) as fd:
            test_email = fd.read()
        ticket = helpdesk.email.object_from_message(test_email, self.queue_public, self.logger)
        self.assertEqual(ticket.title, "Testovácí email")
        self.assertEqual(ticket.description, "íářčšáíéřášč")


class GetEmailParametricTemplate(object):
    """TestCase that checks basic email functionality across methods and socks configs."""

    def setUp(self):

        self.temp_logdir = mkdtemp()
        kwargs = {
            "title": 'Basic Queue',
            "slug": 'QQ',
            "allow_public_submission": True,
            "allow_email_submission": True,
            "email_box_type": self.method,
            "logging_dir": self.temp_logdir,
            "logging_type": 'none'
        }

        if self.method == 'local':
            kwargs["email_box_local_dir"] = '/var/lib/mail/helpdesk/'
        else:
            kwargs["email_box_host"] = unrouted_email_server
            kwargs["email_box_port"] = unused_port

        if self.socks:
            kwargs["socks_proxy_type"] = self.socks
            kwargs["socks_proxy_host"] = unrouted_socks_server
            kwargs["socks_proxy_port"] = unused_port

        self.queue_public = Queue.objects.create(**kwargs)

    def tearDown(self):

        rmtree(self.temp_logdir)

    def test_read_plain_email(self):
        """Tests reading plain text emails from a queue and creating tickets.
           For each email source supported, we mock the backend to provide
           authentically formatted responses containing our test data."""

        # example email text from Django docs: https://docs.djangoproject.com/en/1.10/ref/unicode/
        test_email_from = "Arnbjörg Ráðormsdóttir <arnbjorg@example.com>"
        test_email_subject = "My visit to Sør-Trøndelag"
        test_email_body = "Unicode helpdesk comment with an s-hat (ŝ) via email."
        test_email = "To: helpdesk@example.com\nFrom: " + test_email_from + "\nSubject: " + test_email_subject + "\n\n" + test_email_body
        test_mail_len = len(test_email)

        if self.socks:
            from socks import ProxyConnectionError
            with self.assertRaisesRegex(ProxyConnectionError, '%s:%s' % (unrouted_socks_server, unused_port)):
                call_command('get_email')

        else:
            # Test local email reading
            if self.method == 'local':
                with mock.patch('helpdesk.email.listdir') as mocked_listdir, \
                        mock.patch('helpdesk.email.isfile') as mocked_isfile, \
                        mock.patch('builtins.open', mock.mock_open(read_data=test_email)):
                    mocked_isfile.return_value = True
                    mocked_listdir.return_value = ['filename1', 'filename2']

                    call_command('get_email')

                    mocked_listdir.assert_called_with('/var/lib/mail/helpdesk/')
                    mocked_isfile.assert_any_call('/var/lib/mail/helpdesk/filename1')
                    mocked_isfile.assert_any_call('/var/lib/mail/helpdesk/filename2')

            elif self.method == 'pop3':
                # mock poplib.POP3's list and retr methods to provide responses as per RFC 1939
                pop3_emails = {
                    '1': ("+OK", test_email.split('\n')),
                    '2': ("+OK", test_email.split('\n')),
                }
                pop3_mail_list = ("+OK 2 messages", ("1 %d" % test_mail_len, "2 %d" % test_mail_len))
                mocked_poplib_server = mock.Mock()
                mocked_poplib_server.list = mock.Mock(return_value=pop3_mail_list)
                mocked_poplib_server.retr = mock.Mock(side_effect=lambda x: pop3_emails[x])
                with mock.patch('helpdesk.email.poplib', autospec=True) as mocked_poplib:
                    mocked_poplib.POP3 = mock.Mock(return_value=mocked_poplib_server)
                    call_command('get_email')

            elif self.method == 'imap':
                # mock imaplib.IMAP4's search and fetch methods with responses from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", test_email),)),
                    "2": ("OK", (("2", test_email),)),
                }
                imap_mail_list = ("OK", ("1 2",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(return_value=imap_mail_list)

                # we ignore the second arg as the data item/mime-part is constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(side_effect=lambda x, _: imap_emails[x])
                with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                    mocked_imaplib.IMAP4 = mock.Mock(return_value=mocked_imaplib_server)
                    call_command('get_email')

            ticket1 = get_object_or_404(Ticket, pk=1)
            self.assertEqual(ticket1.ticket_for_url, "QQ-%s" % ticket1.id)
            self.assertEqual(ticket1.title, test_email_subject)
            self.assertEqual(ticket1.description, test_email_body)

            ticket2 = get_object_or_404(Ticket, pk=2)
            self.assertEqual(ticket2.ticket_for_url, "QQ-%s" % ticket2.id)
            self.assertEqual(ticket2.title, test_email_subject)
            self.assertEqual(ticket2.description, test_email_body)

    def test_read_email_with_template_tag(self):
        """Tests reading plain text emails from a queue and creating tickets,
           except this time the email body contains a Django template tag.
           For each email source supported, we mock the backend to provide
           authentically formatted responses containing our test data."""

        # example email text from Django docs: https://docs.djangoproject.com/en/1.10/ref/unicode/
        test_email_from = "Arnbjörg Ráðormsdóttir <arnbjorg@example.com>"
        test_email_subject = "My visit to Sør-Trøndelag"
        test_email_body = "Reporting some issue with the template tag: {% if helpdesk %}."
        test_email = "To: helpdesk@example.com\nFrom: " + test_email_from + "\nSubject: " + test_email_subject + "\n\n" + test_email_body
        test_mail_len = len(test_email)

        if self.socks:
            from socks import ProxyConnectionError
            with self.assertRaisesRegex(ProxyConnectionError, '%s:%s' % (unrouted_socks_server, unused_port)):
                call_command('get_email')

        else:
            # Test local email reading
            if self.method == 'local':
                with mock.patch('helpdesk.email.listdir') as mocked_listdir, \
                        mock.patch('helpdesk.email.isfile') as mocked_isfile, \
                        mock.patch('builtins.open', mock.mock_open(read_data=test_email)):
                    mocked_isfile.return_value = True
                    mocked_listdir.return_value = ['filename1', 'filename2']

                    call_command('get_email')

                    mocked_listdir.assert_called_with('/var/lib/mail/helpdesk/')
                    mocked_isfile.assert_any_call('/var/lib/mail/helpdesk/filename1')
                    mocked_isfile.assert_any_call('/var/lib/mail/helpdesk/filename2')

            elif self.method == 'pop3':
                # mock poplib.POP3's list and retr methods to provide responses as per RFC 1939
                pop3_emails = {
                    '1': ("+OK", test_email.split('\n')),
                    '2': ("+OK", test_email.split('\n')),
                }
                pop3_mail_list = ("+OK 2 messages", ("1 %d" % test_mail_len, "2 %d" % test_mail_len))
                mocked_poplib_server = mock.Mock()
                mocked_poplib_server.list = mock.Mock(return_value=pop3_mail_list)
                mocked_poplib_server.retr = mock.Mock(side_effect=lambda x: pop3_emails[x])
                with mock.patch('helpdesk.email.poplib', autospec=True) as mocked_poplib:
                    mocked_poplib.POP3 = mock.Mock(return_value=mocked_poplib_server)
                    call_command('get_email')

            elif self.method == 'imap':
                # mock imaplib.IMAP4's search and fetch methods with responses from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", test_email),)),
                    "2": ("OK", (("2", test_email),)),
                }
                imap_mail_list = ("OK", ("1 2",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(return_value=imap_mail_list)

                # we ignore the second arg as the data item/mime-part is constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(side_effect=lambda x, _: imap_emails[x])
                with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                    mocked_imaplib.IMAP4 = mock.Mock(return_value=mocked_imaplib_server)
                    call_command('get_email')

            ticket1 = get_object_or_404(Ticket, pk=1)
            self.assertEqual(ticket1.ticket_for_url, "QQ-%s" % ticket1.id)
            self.assertEqual(ticket1.title, test_email_subject)
            self.assertEqual(ticket1.description, test_email_body)

            ticket2 = get_object_or_404(Ticket, pk=2)
            self.assertEqual(ticket2.ticket_for_url, "QQ-%s" % ticket2.id)
            self.assertEqual(ticket2.title, test_email_subject)
            self.assertEqual(ticket2.description, test_email_body)

    def test_read_html_multipart_email(self):
        """Tests reading multipart MIME (HTML body and plain text alternative)
           emails from a queue and creating tickets.
           For each email source supported, we mock the backend to provide
           authentically formatted responses containing our test data."""

        # example email text from Python docs: https://docs.python.org/3/library/email-examples.html
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        me = "my@example.com"
        you = "your@example.com"
        # NOTE: CC'd emails need to be alphabetical and tested as such!
        # implementation uses sets, so only way to ensure tickets created
        # in right order is to change set to list and sort it
        cc_one = "nobody@example.com"
        cc_two = "other@example.com"
        cc = cc_one + ", " + cc_two
        subject = "Link"

        # Create message container - the correct MIME type is multipart/alternative.
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = me
        msg['To'] = you
        msg['Cc'] = cc

        # Create the body of the message (a plain-text and an HTML version).
        text = "Hi!\nHow are you?\nHere is the link you wanted:\nhttps://www.python.org"
        html = """\
        <html>
        <head></head>
        <body>
            <p>Hi!<br>
            How are you?<br>
            Here is the <a href="https://www.python.org">link</a> you wanted.
            </p>
        </body>
        </html>
        """

        # Record the MIME types of both parts - text/plain and text/html.
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')

        # Attach parts into message container.
        # According to RFC 2046, the last part of a multipart message, in this case
        # the HTML message, is best and preferred.
        msg.attach(part1)
        msg.attach(part2)

        test_mail_len = len(msg)

        if self.socks:
            from socks import ProxyConnectionError
            with self.assertRaisesRegex(ProxyConnectionError, '%s:%s' % (unrouted_socks_server, unused_port)):
                call_command('get_email')

        else:
            # Test local email reading
            if self.method == 'local':
                with mock.patch('helpdesk.email.listdir') as mocked_listdir, \
                        mock.patch('helpdesk.email.isfile') as mocked_isfile, \
                        mock.patch('builtins.open', mock.mock_open(read_data=msg.as_string())):
                    mocked_isfile.return_value = True
                    mocked_listdir.return_value = ['filename1', 'filename2']

                    call_command('get_email')

                    mocked_listdir.assert_called_with('/var/lib/mail/helpdesk/')
                    mocked_isfile.assert_any_call('/var/lib/mail/helpdesk/filename1')
                    mocked_isfile.assert_any_call('/var/lib/mail/helpdesk/filename2')

            elif self.method == 'pop3':
                # mock poplib.POP3's list and retr methods to provide responses as per RFC 1939
                pop3_emails = {
                    '1': ("+OK", msg.as_string().split('\n')),
                    '2': ("+OK", msg.as_string().split('\n')),
                }
                pop3_mail_list = ("+OK 2 messages", ("1 %d" % test_mail_len, "2 %d" % test_mail_len))
                mocked_poplib_server = mock.Mock()
                mocked_poplib_server.list = mock.Mock(return_value=pop3_mail_list)
                mocked_poplib_server.retr = mock.Mock(side_effect=lambda x: pop3_emails[x])
                with mock.patch('helpdesk.email.poplib', autospec=True) as mocked_poplib:
                    mocked_poplib.POP3 = mock.Mock(return_value=mocked_poplib_server)
                    call_command('get_email')

            elif self.method == 'imap':
                # mock imaplib.IMAP4's search and fetch methods with responses from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", msg.as_string()),)),
                    "2": ("OK", (("2", msg.as_string()),)),
                }
                imap_mail_list = ("OK", ("1 2",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(return_value=imap_mail_list)

                # we ignore the second arg as the data item/mime-part is constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(side_effect=lambda x, _: imap_emails[x])
                with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                    mocked_imaplib.IMAP4 = mock.Mock(return_value=mocked_imaplib_server)
                    call_command('get_email')

            ticket1 = get_object_or_404(Ticket, pk=1)
            self.assertEqual(ticket1.ticket_for_url, "QQ-%s" % ticket1.id)
            self.assertEqual(ticket1.title, subject)
            # plain text should become description
            self.assertEqual(ticket1.description, text)
            # HTML MIME part should be attached to follow up
            followup1 = get_object_or_404(FollowUp, pk=1)
            self.assertEqual(followup1.ticket.id, 1)
            attach1 = get_object_or_404(FollowUpAttachment, pk=1)
            self.assertEqual(attach1.followup.id, 1)
            self.assertEqual(attach1.filename, 'email_html_body.html')
            cc0 = get_object_or_404(TicketCC, pk=1)
            self.assertEqual(cc0.email, you)
            cc1 = get_object_or_404(TicketCC, pk=2)
            self.assertEqual(cc1.email, cc_one)
            cc2 = get_object_or_404(TicketCC, pk=3)
            self.assertEqual(cc2.email, cc_two)
            self.assertEqual(len(TicketCC.objects.filter(ticket=1)), 3)

            ticket2 = get_object_or_404(Ticket, pk=2)
            self.assertEqual(ticket2.ticket_for_url, "QQ-%s" % ticket2.id)
            self.assertEqual(ticket2.title, subject)
            # plain text should become description
            self.assertEqual(ticket2.description, text)
            # HTML MIME part should be attached to follow up
            followup2 = get_object_or_404(FollowUp, pk=2)
            self.assertEqual(followup2.ticket.id, 2)
            attach2 = get_object_or_404(FollowUpAttachment, pk=2)
            self.assertEqual(attach2.followup.id, 2)
            self.assertEqual(attach2.filename, 'email_html_body.html')

    def test_read_pgp_signed_email(self):
        """Tests reading a PGP signed email to ensure we handle base64
           and PGP signatures appropriately."""

        # example email text from #567 on GitHub
        with open(os.path.join(THIS_DIR, "test_files/pgp.eml")) as fd:
            test_email = fd.read()
        test_mail_len = len(test_email)

        if self.socks:
            from socks import ProxyConnectionError
            with self.assertRaisesRegex(ProxyConnectionError, '%s:%s' % (unrouted_socks_server, unused_port)):
                call_command('get_email')

        else:
            # Test local email reading
            if self.method == 'local':
                with mock.patch('helpdesk.email.listdir') as mocked_listdir, \
                        mock.patch('helpdesk.email.isfile') as mocked_isfile, \
                        mock.patch('builtins.open', mock.mock_open(read_data=test_email)):
                    mocked_isfile.return_value = True
                    mocked_listdir.return_value = ['filename1']

                    call_command('get_email')

                    mocked_listdir.assert_called_with('/var/lib/mail/helpdesk/')
                    mocked_isfile.assert_any_call('/var/lib/mail/helpdesk/filename1')

            elif self.method == 'pop3':
                # mock poplib.POP3's list and retr methods to provide responses as per RFC 1939
                pop3_emails = {
                    '1': ("+OK", test_email.split('\n')),
                }
                pop3_mail_list = ("+OK 1 message", ("1 %d" % test_mail_len))
                mocked_poplib_server = mock.Mock()
                mocked_poplib_server.list = mock.Mock(return_value=pop3_mail_list)
                mocked_poplib_server.retr = mock.Mock(side_effect=lambda x: pop3_emails['1'])
                with mock.patch('helpdesk.email.poplib', autospec=True) as mocked_poplib:
                    mocked_poplib.POP3 = mock.Mock(return_value=mocked_poplib_server)
                    call_command('get_email')

            elif self.method == 'imap':
                # mock imaplib.IMAP4's search and fetch methods with responses from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", test_email),)),
                }
                imap_mail_list = ("OK", ("1",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(return_value=imap_mail_list)

                # we ignore the second arg as the data item/mime-part is constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(side_effect=lambda x, _: imap_emails[x])
                with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                    mocked_imaplib.IMAP4 = mock.Mock(return_value=mocked_imaplib_server)
                    call_command('get_email')

            ticket1 = get_object_or_404(Ticket, pk=1)
            self.assertEqual(ticket1.ticket_for_url, "QQ-%s" % ticket1.id)
            self.assertEqual(ticket1.title, "example email that crashes django-helpdesk get_email")
            self.assertEqual(ticket1.description, """hi, thanks for looking into this :)\n\nhttps://github.com/django-helpdesk/django-helpdesk/issues/567#issuecomment-342954233""")
            # MIME part should be attached to follow up
            followup1 = get_object_or_404(FollowUp, pk=1)
            self.assertEqual(followup1.ticket.id, 1)
            attach1 = get_object_or_404(FollowUpAttachment, pk=1)
            self.assertEqual(attach1.followup.id, 1)
            self.assertEqual(attach1.filename, 'signature.asc')
            self.assertEqual(attach1.file.read(), b"""-----BEGIN PGP SIGNATURE-----

iQIcBAEBCAAGBQJaA3dnAAoJELBLc7QPITnLN54P/3Zsu7+AIQWDFTvziJfCqswG
u99fG+iWa6ER+iuZG0YU1BdIxIjSKt1pvqB0yXITlT9FCdf1zc0pmeJ08I0a5pVa
iaym5prVUro5BNQ6Vqoo0jvOCKNrACtFNv85zDzXbPNP8TrUss41U+ackPHkOHov
cmJ5YZFQebYXXpibFSIDimVGfwI57vyTWvolttZFLSI1mgGX7MvHaKh253QLdXIo
EUih40rOw3f/nYPEKyW8QA72ImBsZdcZI5buiiCC1bgMkKSFSNAFiIanYEpGNMnO
3zYKBpbpBhnWSi5orwx47/v4/Yb/qVr5ppuV23+YoMfEGT8cHPTAdYpnpE27ByAv
jvpxKEwmkUzD1WxOmQdCcPJPyWz1OBUVvjj0nn0Espnz8V8esl9+IFs739lpFBHu
fWWA315LTmIJMGH5Ujf4myiQeXDo6Gsy6WhE13q7MKTq3tnyi5dJG9GJCBf646dL
RwcDf9O7MvKSV2kSPmryLnUF7D+2fva+Cy+CvJDVJCo5zr4ucXPXZ4htpI6Pjpd5
oPHvbqxSCMJrQ7eAFTYmBNGauSyr0XvGM1qmHBZD/laQEJHYgLT2ILrymZhVDHtK
W7tXhGjMoUvqAxiKkmG3UHFqN4k3EYo13PwoOWyJHD1M9ArbX/Sk9l8DDguCh3DW
a9eiiQ+3V1v+7wWHXCzq
=6JeP
-----END PGP SIGNATURE-----
""")
            # should this be 'application/pgp-signature'?
            # self.assertEqual(attach1.mime_type, 'text/plain')


class GetEmailCCHandling(TestCase):
    """TestCase that checks CC handling in email. Needs its own test harness."""

    def setUp(self):

        self.temp_logdir = mkdtemp()

        kwargs = {
            "title": 'CC Queue',
            "slug": 'CC',
            "allow_public_submission": True,
            "allow_email_submission": True,
            "email_address": 'queue@example.com',
            "email_box_type": 'local',
            "email_box_local_dir": '/var/lib/mail/helpdesk/',
            "logging_dir": self.temp_logdir,
            "logging_type": 'none'
        }
        self.queue_public = Queue.objects.create(**kwargs)

        user1_kwargs = {
            'username': 'staff',
            'email': 'staff@example.com',
            'password': make_password('Test1234'),
            'is_staff': True,
            'is_superuser': False,
            'is_active': True
        }
        self.staff_user = User.objects.create(**user1_kwargs)

        user2_kwargs = {
            'username': 'assigned',
            'email': 'assigned@example.com',
            'password': make_password('Test1234'),
            'is_staff': True,
            'is_superuser': False,
            'is_active': True
        }
        self.assigned_user = User.objects.create(**user2_kwargs)

        user3_kwargs = {
            'username': 'observer',
            'email': 'observer@example.com',
            'password': make_password('Test1234'),
            'is_staff': True,
            'is_superuser': False,
            'is_active': True
        }
        self.observer_user = User.objects.create(**user3_kwargs)

        ticket_kwargs = {
            'title': 'Original Ticket',
            'queue': self.queue_public,
            'submitter_email': 'submitter@example.com',
            'assigned_to': self.assigned_user,
            'status': 1
        }
        self.original_ticket = Ticket.objects.create(**ticket_kwargs)

        cc_kwargs = {
            'ticket': self.original_ticket,
            'user': self.staff_user,
            'can_view': True,
            'can_update': True
        }
        self.original_cc = TicketCC.objects.create(**cc_kwargs)

    def tearDown(self):

        rmtree(self.temp_logdir)

    def test_read_email_cc(self):
        """Tests reading plain text emails from a queue and adding to a ticket,
           particularly to test appropriate handling of CC'd emails."""

        # first, check that test ticket exists
        ticket1 = get_object_or_404(Ticket, pk=1)
        self.assertEqual(ticket1.ticket_for_url, "CC-1")
        self.assertEqual(ticket1.title, "Original Ticket")
        # only the staff_user is CC'd for now
        self.assertEqual(len(TicketCC.objects.filter(ticket=1)), 1)
        ccstaff = get_object_or_404(TicketCC, pk=1)
        self.assertEqual(ccstaff.user, User.objects.get(username='staff'))
        self.assertEqual(ticket1.assigned_to, User.objects.get(username='assigned'))

        # example email text from Django docs: https://docs.djangoproject.com/en/1.10/ref/unicode/
        test_email_from = "submitter@example.com"
        # NOTE: CC emails are in alphabetical order and must be tested as such!
        # implementation uses sets, so only way to ensure tickets created
        # in right order is to change set to list and sort it
        test_email_cc_one = "Alice Ráðormsdóttir <alice@example.com>"
        test_email_cc_two = "nobody@example.com"
        test_email_cc_three = "other@example.com"
        test_email_cc_four = "someone@example.com"
        ticket_user_emails = "assigned@example.com, staff@example.com, submitter@example.com, observer@example.com, queue@example.com"
        test_email_subject = "[CC-1] My visit to Sør-Trøndelag"
        test_email_body = "Unicode helpdesk comment with an s-hat (ŝ) via email."
        test_email = "To: queue@example.com\nCc: " + test_email_cc_one + ", " + test_email_cc_one + ", " + test_email_cc_two + ", " + test_email_cc_three + "\nCC: " + test_email_cc_one + ", " + test_email_cc_three + ", " + test_email_cc_four + ", " + ticket_user_emails + "\nFrom: " + test_email_from + "\nSubject: " + test_email_subject + "\n\n" + test_email_body
        test_mail_len = len(test_email)

        with mock.patch('helpdesk.email.listdir') as mocked_listdir, \
                mock.patch('helpdesk.email.isfile') as mocked_isfile, \
                mock.patch('builtins.open', mock.mock_open(read_data=test_email)):

            mocked_isfile.return_value = True
            mocked_listdir.return_value = ['filename1']

            call_command('get_email')

            mocked_listdir.assert_called_with('/var/lib/mail/helpdesk/')
            mocked_isfile.assert_any_call('/var/lib/mail/helpdesk/filename1')

        # 9 unique email addresses are CC'd when all is done
        self.assertEqual(len(TicketCC.objects.filter(ticket=1)), 9)
        # next we make sure no duplicates were added, and the
        # staff users nor submitter were not re-added as email TicketCCs
        cc1 = get_object_or_404(TicketCC, pk=1)
        self.assertEqual(cc1.user, User.objects.get(username='staff'))
        cc2 = get_object_or_404(TicketCC, pk=2)
        self.assertEqual(cc2.email, "alice@example.com")
        cc3 = get_object_or_404(TicketCC, pk=3)
        self.assertEqual(cc3.email, test_email_cc_two)
        cc4 = get_object_or_404(TicketCC, pk=4)
        self.assertEqual(cc4.email, test_email_cc_three)
        cc5 = get_object_or_404(TicketCC, pk=5)
        self.assertEqual(cc5.email, test_email_cc_four)
        cc6 = get_object_or_404(TicketCC, pk=6)
        self.assertEqual(cc6.email, "assigned@example.com")
        cc7 = get_object_or_404(TicketCC, pk=7)
        self.assertEqual(cc7.email, "staff@example.com")
        cc8 = get_object_or_404(TicketCC, pk=8)
        self.assertEqual(cc8.email, "submitter@example.com")
        cc9 = get_object_or_404(TicketCC, pk=9)
        self.assertEqual(cc9.user, User.objects.get(username='observer'))
        self.assertEqual(cc9.email, "observer@example.com")


# build matrix of test cases
case_methods = [c[0] for c in Queue._meta.get_field('email_box_type').choices]
case_socks = [False] + [c[0] for c in Queue._meta.get_field('socks_proxy_type').choices]
case_matrix = list(itertools.product(case_methods, case_socks))

# Populate TestCases from the matrix of parameters
thismodule = sys.modules[__name__]
for method, socks in case_matrix:

    if method == "local" and socks:
        continue

    socks_str = "Nosocks"
    if socks:
        socks_str = socks.capitalize()
    test_name = str(
        "TestGetEmail%s%s" % (method.capitalize(), socks_str))

    cl = type(test_name, (GetEmailParametricTemplate, TestCase), {"method": method, "socks": socks})
    setattr(thismodule, test_name, cl)
