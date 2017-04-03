from __future__ import unicode_literals

from helpdesk.models import Queue, Ticket, FollowUp, Attachment
from django.test import TestCase
from django.core.management import call_command
from django.utils import six
from django.shortcuts import get_object_or_404
import itertools
from shutil import rmtree
import sys
from tempfile import mkdtemp

try:  # python 3
    from urllib.parse import urlparse
except ImportError:  # python 2
    from urlparse import urlparse

try:
    # Python >= 3.3
    from unittest import mock
except ImportError:
    # Python < 3.3
    import mock

# class A addresses can't have first octet of 0
unrouted_socks_server = "0.0.0.1"
unrouted_email_server = "0.0.0.1"
# the last user port, reserved by IANA
unused_port = "49151"


class GetEmailCommonTests(TestCase):

    # tests correct syntax for command line option
    def test_get_email_quiet_option(self):
        """Test quiet option is properly propagated"""
        with mock.patch('helpdesk.management.commands.get_email.process_email') as mocked_processemail:
            call_command('get_email', quiet=True)
            mocked_processemail.assert_called_with(quiet=True)
            call_command('get_email')
            mocked_processemail.assert_called_with(quiet=False)


class GetEmailParametricTemplate(object):
    """TestCase that checks email functionality across methods and socks configs."""

    def setUp(self):

        self.temp_logdir = mkdtemp()
        kwargs = {
            "title": 'Queue 1',
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
            with self.assertRaisesRegexp(ProxyConnectionError, '%s:%s' % (unrouted_socks_server, unused_port)):
                call_command('get_email')

        else:
            # Test local email reading
            if self.method == 'local':
                with mock.patch('helpdesk.management.commands.get_email.listdir') as mocked_listdir, \
                        mock.patch('helpdesk.management.commands.get_email.isfile') as mocked_isfile, \
                        mock.patch('builtins.open' if six.PY3 else '__builtin__.open', mock.mock_open(read_data=test_email)):
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
                with mock.patch('helpdesk.management.commands.get_email.poplib', autospec=True) as mocked_poplib:
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
                with mock.patch('helpdesk.management.commands.get_email.imaplib', autospec=True) as mocked_imaplib:
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
        subject = "Link"

        # Create message container - the correct MIME type is multipart/alternative.
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = me
        msg['To'] = you

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
            with self.assertRaisesRegexp(ProxyConnectionError, '%s:%s' % (unrouted_socks_server, unused_port)):
                call_command('get_email')

        else:
            # Test local email reading
            if self.method == 'local':
                with mock.patch('helpdesk.management.commands.get_email.listdir') as mocked_listdir, \
                        mock.patch('helpdesk.management.commands.get_email.isfile') as mocked_isfile, \
                        mock.patch('builtins.open' if six.PY3 else '__builtin__.open', mock.mock_open(read_data=msg.as_string())):
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
                with mock.patch('helpdesk.management.commands.get_email.poplib', autospec=True) as mocked_poplib:
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
                with mock.patch('helpdesk.management.commands.get_email.imaplib', autospec=True) as mocked_imaplib:
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
            attach1 = get_object_or_404(Attachment, pk=1)
            self.assertEqual(attach1.followup.id, 1)
            self.assertEqual(attach1.filename, 'email_html_body.html')

            ticket2 = get_object_or_404(Ticket, pk=2)
            self.assertEqual(ticket2.ticket_for_url, "QQ-%s" % ticket2.id)
            self.assertEqual(ticket2.title, subject)
            # plain text should become description
            self.assertEqual(ticket2.description, text)
            # HTML MIME part should be attached to follow up
            followup2 = get_object_or_404(FollowUp, pk=2)
            self.assertEqual(followup2.ticket.id, 2)
            attach2 = get_object_or_404(Attachment, pk=2)
            self.assertEqual(attach2.followup.id, 2)
            self.assertEqual(attach2.filename, 'email_html_body.html')


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

    cl = type(test_name, (GetEmailParametricTemplate, TestCase,), {
        "method": method,
        "socks": socks})
    setattr(thismodule, test_name, cl)
