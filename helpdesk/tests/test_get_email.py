from helpdesk.models import Queue, Ticket
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
    """TestCase that checks email functionality accross methods and socks configs."""

    def setUp(self):

        self.temp_logdir = mkdtemp()
        kwargs = {
            "title": 'Queue 1',
            "slug": 'QQ',
            "allow_public_submission": True,
            "allow_email_submission": True,
            "email_box_type": self.method,
            "logging_dir": self.temp_logdir,
            "logging_type": 'none'}

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

    def test_read_email(self):
        """Tests reading emails from a queue and creating tickets.
           For each email source supported, we mock the backend to provide
           authenticly formatted responses containing our test data."""
        test_email = "To: update.public@example.com\nFrom: comment@example.com\nSubject: Some Comment\n\nThis is the helpdesk comment via email."
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
                    try:
                        call_command('get_email')
                    except UnboundLocalError:
                        # known bug fixed by a subsequent commit
                        return True

            ticket1 = get_object_or_404(Ticket, pk=1)
            self.assertEqual(ticket1.ticket_for_url, "QQ-%s" % ticket1.id)
            self.assertEqual(ticket1.description, "This is the helpdesk comment via email.")

            ticket2 = get_object_or_404(Ticket, pk=2)
            self.assertEqual(ticket2.ticket_for_url, "QQ-%s" % ticket2.id)
            self.assertEqual(ticket2.description, "This is the helpdesk comment via email.")

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
