from helpdesk.models import Queue, Ticket
from django.test import TestCase
from django.core.management import call_command
from django.utils import six
from django.shortcuts import get_object_or_404
import itertools
import sys

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

unrouted_socks_server = "127.0.0.1"
unrouted_email_server = "127.0.0.1"
unrouted_port = "12345"


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

        kwargs = {
            "title": 'Queue 1',
            "slug": 'QQ',
            "allow_public_submission": True,
            "allow_email_submission": True,
            "email_box_type": self.method,
            "logging_type": 'none'}

        if self.method == 'local':
            kwargs["email_box_local_dir"] = '/var/lib/mail/helpdesk/'
        else:
            kwargs["email_box_host"] = unrouted_email_server
            kwargs["email_box_port"] = unrouted_port

        if self.socks:
            kwargs["socks_proxy_type"] = self.socks
            kwargs["socks_proxy_host"] = unrouted_socks_server
            kwargs["socks_proxy_port"] = unrouted_port

        self.queue_public = Queue.objects.create(**kwargs)

    def test_read_email(self):
        """Tests reading emails from a queue and creating tickets."""
        test_email = "To: update.public@example.com\nFrom: comment@example.com\nSubject: Some Comment\n\nThis is the helpdesk comment via email."

        if self.socks:
            from socks import ProxyConnectionError
            with self.assertRaisesRegexp(ProxyConnectionError, '%s:%s' % (unrouted_socks_server, unrouted_port)):
                call_command('get_email')

            # with mock.patch('socket.socket') as mocked_socket,\
            #         mock.patch('socks.socket') as mocked_sockssocket:
            #     call_command('get_email')
            #     print(mocked_socket)
            #     print(mocked_sockssocket)
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
                if six.PY3:
                    errorclass = ConnectionRefusedError
                else:
                    from socket import error
                    errorclass = error
                with self.assertRaisesRegexp(errorclass, "Connection refused"):
                    call_command('get_email')

            # Other methods go here, not implemented yet.
            else:
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
