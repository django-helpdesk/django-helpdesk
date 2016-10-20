from helpdesk.models import Queue, Ticket
from helpdesk.management.commands.get_email import process_email
from django.test import TestCase
from django.core import mail
from django.core.management import call_command
from django.test.client import Client
from django.utils import six
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404

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

class GetEmailTestCase(TestCase):
    #fixtures = ['emailtemplate.json'] # may don't need this, not testing templates here

    def setUp(self):
        self.queue_public = Queue.objects.create(title='Queue 1', slug='QQ', allow_public_submission=True, allow_email_submission=True, email_box_type='local', email_box_local_dir='/var/lib/mail/helpdesk/')

    # tests correct syntax for command line option
    def test_get_email_quiet_option(self):
        with mock.patch('helpdesk.management.commands.get_email.process_email') as mocked_processemail:
            call_command('get_email', quiet=True)
            mocked_processemail.assert_called_with(quiet=True)
            call_command('get_email')
            mocked_processemail.assert_called_with(quiet=False)

    # tests reading emails from a queue and creating tickets
    def test_read_email(self):
        test_email = "To: update.public@example.com\nFrom: comment@example.com\nSubject: Some Comment\n\nThis is the helpdesk comment via email."
        with mock.patch('helpdesk.management.commands.get_email.listdir') as mocked_listdir, \
                mock.patch('helpdesk.management.commands.get_email.isfile') as mocked_isfile, \
                mock.patch('builtins.open' if six.PY3 else '__builtin__.open', mock.mock_open(read_data=test_email)):
            mocked_isfile.return_value = True
            mocked_listdir.return_value = ['filename1', 'filename2']

            call_command('get_email')

            mocked_listdir.assert_called_with('/var/lib/mail/helpdesk/')
            mocked_isfile.assert_any_call('/var/lib/mail/helpdesk/filename1')
            mocked_isfile.assert_any_call('/var/lib/mail/helpdesk/filename2')

            ticket1 = get_object_or_404(Ticket, pk=1)
            self.assertEqual(ticket1.ticket_for_url, "QQ-%s" % ticket1.id)
            self.assertEqual(ticket1.description, "This is the helpdesk comment via email.")

            ticket2 = get_object_or_404(Ticket, pk=2)
            self.assertEqual(ticket2.ticket_for_url, "QQ-%s" % ticket2.id)
            self.assertEqual(ticket2.description, "This is the helpdesk comment via email.")



