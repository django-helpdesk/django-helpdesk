# -*- coding: utf-8 -*-

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.shortcuts import get_object_or_404
from django.test import override_settings, TestCase
from email.mime.message import MIMEMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import helpdesk.email
from helpdesk.email import extract_email_metadata, process_as_attachment
from helpdesk.exceptions import DeleteIgnoredTicketException, IgnoreTicketException
from helpdesk.management.commands.get_email import Command
from helpdesk.models import FollowUp, FollowUpAttachment, IgnoreEmail, Queue, Ticket, TicketCC
from helpdesk.tests import utils
import itertools
import logging
from mock.mock import patch
from oauthlib.oauth2 import BackendApplicationClient
import os
from shutil import rmtree
import sys
from tempfile import mkdtemp
import time
import typing
from unittest import mock


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
# class A addresses can't have first octet of 0
unrouted_socks_server = "0.0.0.1"
unrouted_email_server = "0.0.0.1"
# the last user port, reserved by IANA
unused_port = "49151"

fake_time = time.time()


class GetEmailCommonTests(TestCase):

    def setUp(self):
        self.queue_public = Queue.objects.create(title='Test', slug='test')
        self.logger = logging.getLogger('helpdesk')
    # tests correct syntax for command line option
    def test_get_email_quiet_option(self):
        """Test quiet option is properly propagated"""
        # Test get_email with quiet set to True and also False, and verify
        # handle receives quiet option set properly
        for quiet_test_value in [True, False]:
            with mock.patch.object(Command, 'handle', return_value=None) as mocked_handle:
                call_command('get_email', quiet=quiet_test_value)
                mocked_handle.assert_called_once()
                for _, kwargs in mocked_handle.call_args_list:
                    self.assertEqual(quiet_test_value, (kwargs['quiet']))

    def test_email_with_blank_body_and_attachment(self):
        """
        Tests that emails with blank bodies and attachments work.
        https://github.com/django-helpdesk/django-helpdesk/issues/700
        """
        with open(os.path.join(THIS_DIR, "test_files/blank-body-with-attachment.eml"), encoding="utf-8") as fd:
            test_email = fd.read()
            ticket = helpdesk.email.extract_email_metadata(
                test_email, self.queue_public, self.logger)
        # title got truncated because of max_lengh of the model.title field
        assert ticket.title == (
            "Attachment without body - and a loooooooooooooooooooooooooooooooooo"
            "ooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooo"
            "ooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooo..."
        )
        self.assertEqual(ticket.description.strip(), "", msg=ticket.description)

    def test_email_with_quoted_printable_body(self):
        """
        Tests that emails with quoted-printable bodies work.
        """
        with open(os.path.join(THIS_DIR, "test_files/quoted_printable.eml"), encoding="utf-8") as fd:
            test_email = fd.read()
            ticket = helpdesk.email.extract_email_metadata(
                test_email, self.queue_public, self.logger)
        self.assertEqual(ticket.title, "Český test")
        self.assertEqual(ticket.description,
                         "Tohle je test českých písmen odeslaných z gmailu.")
        followups = FollowUp.objects.filter(ticket=ticket)
        self.assertEqual(len(followups), 1)
        followup = followups[0]
        attachments = FollowUpAttachment.objects.filter(followup=followup)
        self.assertEqual(len(attachments), 1)
        attachment = attachments[0]
        self.assertIn('<div dir="ltr">Tohle je test českých písmen odeslaných z gmailu.</div>\n',
                      attachment.file.read().decode("utf-8"))

    def test_email_with_8bit_encoding_and_utf_8(self):
        """
        Tests that emails with 8bit transfer encoding and utf-8 charset
        https://github.com/django-helpdesk/django-helpdesk/issues/732
        """
        with open(os.path.join(THIS_DIR, "test_files/all-special-chars.eml"), encoding="utf-8") as fd:
            test_email = fd.read()
            ticket = helpdesk.email.extract_email_metadata(
                test_email, self.queue_public, self.logger)
        self.assertEqual(ticket.title, "Testovácí email")
        self.assertEqual(ticket.description, "íářčšáíéřášč")

    @override_settings(HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL=False)
    def test_email_with_utf_8_non_decodable_sequences(self):
        """
        Tests that emails with utf-8 non-decodable sequences are parsed correctly
        The forwarded part of the message must still be in the ticket description if
        HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL is set to True.
        Otherwise it should only be in the Followup records Comment field
        NOTE: This test weirdly tests having completely different content in the HTML part
               than the PLAIN part so not sure about the validity of this as a test but 
               the code does support this oddity anyway for backwards compatibility
        """
        with open(os.path.join(THIS_DIR, "test_files/utf-nondecodable.eml"), encoding="utf-8") as fd:
            test_email = fd.read()
        ticket = helpdesk.email.extract_email_metadata(
            test_email, self.queue_public, self.logger)
        self.assertEqual(
            ticket.title, "Fwd: Cyklozaměstnavatel - změna vyhodnocení")
        self.assertIn("prosazuje lepší", ticket.description, "Missing text \"prosazuje lepší\" in description: %s" % ticket.description)
        followups = FollowUp.objects.filter(ticket=ticket)
        followup = followups[0]
        attachments = FollowUpAttachment.objects.filter(followup=followup)
        attachment = attachments[0]
        self.assertIn('prosazuje lepší',
                      attachment.file.read().decode("utf-8"))

    @override_settings(HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL=True)
    def test_email_with_forwarded_message_just_message_stored(self):
        """
        The forwarded part of the message must still be in the ticket description if
        HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL is set to True.
        Otherwise it should only be in the Followup records Comment field        
        """
        with open(os.path.join(THIS_DIR, "test_files/forwarded-message.eml"), encoding="utf-8") as fd:
            test_email = fd.read()
        ticket = helpdesk.email.extract_email_metadata(
            test_email, self.queue_public, self.logger)
        self.assertEqual(
            ticket.title, "Test with original message from GitHub")
        self.assertIn("This is email body", ticket.description)
        self.assertTrue("Hello there!" in ticket.description, ticket.description)
        self.assertTrue(FollowUp.objects.filter(ticket=ticket).count() == 1)

    @override_settings(HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL=False)
    def test_email_with_forwarded_message_chained_messages_stored(self):
        """
        The forwarded part of the message must still be in the ticket description if
        HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL is set to True.
        Otherwise it should only be in the Followup records Comment field        
        """
        with open(os.path.join(THIS_DIR, "test_files/forwarded-message.eml"), encoding="utf-8") as fd:
            test_email = fd.read()
        ticket = helpdesk.email.extract_email_metadata(
            test_email, self.queue_public, self.logger)
        self.assertEqual(
            ticket.title, "Test with original message from GitHub")
        self.assertIn("This is email body", ticket.description)
        self.assertTrue("Hello there!" not in ticket.description, ticket.description)
        followups = FollowUp.objects.filter(ticket=ticket).values("comment")
        self.assertTrue(followups.count() == 1)
        self.assertTrue("Hello there!" in followups[0]["comment"], followups[0]["comment"])

    def test_will_delete_ignored_email(self):
        """
        Tests if an email will be ignored if configured to do so and throws the correct exception
        to ensure the email is deleted
        """
        message, from_meta, _ = utils.generate_text_email(locale="es_ES")
        ignore = IgnoreEmail(name="Test Ignore", email_address=from_meta[1], keep_in_mailbox=False)
        ignore.save()
        with self.assertRaises(DeleteIgnoredTicketException):
            extract_email_metadata(message.as_string(), self.queue_public, self.logger)

    def test_will_not_delete_ignored_email(self):
        """
        Tests if an email will be ignored if configured to do so and throws the correct exception
        to ensure the email is NOT deleted
        """
        message, from_meta, _ = utils.generate_text_email(locale="es_ES")
        ignore = IgnoreEmail(name="Test Ignore", email_address=from_meta[1], keep_in_mailbox=True)
        ignore.save()
        with self.assertRaises(IgnoreTicketException):
            extract_email_metadata(message.as_string(), self.queue_public, self.logger)

    def test_utf8_filename_attachment(self):
        """
        Tests if an attachment correctly sent with a UTF8 filename in disposition is extracted correctly
        """
        filename = "TeléfonoMañana.txt"
        part = utils.generate_file_mime_part(locale="es_ES", filename=filename)
        files: typing.List[SimpleUploadedFile] = []
        process_as_attachment(part, counter=1, files=files, logger=self.logger)
        sent_file: SimpleUploadedFile = files[0]
        # The extractor prepends a part identifier so compare the ending
        self.assertTrue(sent_file.name.endswith(filename), f"Filename extracted does not match: {sent_file.name}")

    def test_wrong_extension_attachment(self):
        """
        Tests if an attachment with a wrong extension doesn't stop the email process
        """
        message, _, _ = utils.generate_multipart_email(type_list=['plain', 'executable'])

        self.assertEqual(len(mail.outbox), 0)  # @UndefinedVariable

        with self.assertLogs(logger='helpdesk', level='ERROR') as cm:
            extract_email_metadata(message.as_string(), self.queue_public, self.logger)

            self.assertIn(
                "ERROR:helpdesk:['Unsupported file extension: .exe']",
                cm.output
            )

        self.assertEqual(len(mail.outbox), 1)  # @UndefinedVariable
        self.assertEqual(f'[test-1] {message.get("subject")} (Opened)', mail.outbox[0].subject)

    def test_multiple_attachments(self):
        """
        Tests the saving of multiple attachments
        """
        message, _, _ = utils.generate_multipart_email(type_list=['plain', 'file', 'image'])

        self.assertEqual(len(mail.outbox), 0)  # @UndefinedVariable

        extract_email_metadata(message.as_string(), self.queue_public, self.logger)

        self.assertEqual(len(mail.outbox), 1)  # @UndefinedVariable
        self.assertEqual(f'[test-1] {message.get("subject")} (Opened)', mail.outbox[0].subject)

        ticket = Ticket.objects.get()
        followup = ticket.followup_set.get()
        self.assertEqual(2, followup.followupattachment_set.count())

    def test_multiple_attachments_with_wrong_extension(self):
        """
        Tests that a wrong extension won't stop from saving other valid attachment
        """
        message, _, _ = utils.generate_multipart_email(type_list=['plain', 'executable', 'file', 'executable'])

        self.assertEqual(len(mail.outbox), 0)  # @UndefinedVariable

        with self.assertLogs(logger='helpdesk', level='ERROR') as cm:
            extract_email_metadata(message.as_string(), self.queue_public, self.logger)

            self.assertIn(
                "ERROR:helpdesk:['Unsupported file extension: .exe']",
                cm.output
            )

        ticket = Ticket.objects.get()
        followup = ticket.followup_set.get()
        self.assertEqual(1, followup.followupattachment_set.count())

    def test_email_with_multipart_as_attachment(self):
        """
        Is a multipart attachment to an email correctly saved as an attachment
        """
        att_filename = 'email_attachment.eml'
        message, _, _ = utils.generate_multipart_email(type_list=['plain', 'html'])
        email_attachment, _, _ = utils.generate_multipart_email(type_list=['plain', 'html'])
        att_content = email_attachment.as_string()
        message.attach(utils.generate_file_mime_part(filename=att_filename, content=att_content))

        extract_email_metadata(message.as_string(), self.queue_public, self.logger)
        self.assertEqual(len(mail.outbox), 1)  # @UndefinedVariable
        self.assertEqual(f'[test-1] {message.get("subject")} (Opened)', mail.outbox[0].subject)

        ticket = Ticket.objects.get()
        followup = ticket.followup_set.get()

        for att_retrieved in followup.followupattachment_set.all():
            if (helpdesk.email.HTML_EMAIL_ATTACHMENT_FILENAME == att_retrieved.filename):
                # Ignore the HTML formatted conntent of the email that is attached 
                continue
            self.assertTrue(att_retrieved.filename.endswith(att_filename), "Filename of attached multipart not detected: %s" % (att_retrieved.filename))
            with att_retrieved.file.open('r') as f:
                retrieved_content = f.read()
                self.assertEquals(att_content, retrieved_content, "Retrieved attachment content different to original :\n\n%s\n\n%s" % (att_content, retrieved_content))

    def test_email_with_inline_and_multipart_as_attachments(self):
        """
        Test a multipart email with an inline attachment and a multipart email attachment to the email
        """
        inline_att_filename = 'inline_attachment.jpg'
        email_att_filename = 'email_attachment2.eml'
        # Create the inline attachment for the email using an ID so we can reference it in the email body
        inline_image_id = "liTE5er6Dbnd"
        inline_attachment = utils.generate_image_mime_part(locale="en_US", imagename=inline_att_filename, disposition_primary_type="inline")
        inline_attachment.add_header('X-Attachment-Id', inline_image_id)
        inline_attachment.add_header('Content-ID', '<' + inline_image_id + '>')
        # Create the actual email with its plain and HTML parts
        alt_email_message = MIMEMultipart("alternative")
        # Create the plain and HTML that will reference the inline attachment
        plain_body = "Test with inline image: \n[image: " + inline_att_filename + "]\n\n"
        plain_msg = MIMEText(plain_body)
        alt_email_message.attach(plain_msg)
        html_body = '<div><div>Test with inline image: <img src=3D"cid:' + inline_image_id + '" alt=3D="' + inline_att_filename + '"><br></div>'
        html_msg = MIMEText(html_body, "html")
        alt_email_message.attach(html_msg)
        # Create the email to be attached and attach that as well
        email_to_be_attached, _, _ = utils.generate_multipart_email(type_list=['plain', 'html'])
        email_as_attachment = MIMEMessage(email_to_be_attached)
        email_as_attachment.add_header('Content-Disposition', 'attachment', filename=email_att_filename)
        # Now create the base multipart and attach all the other parts to it
        related_message = MIMEMultipart("related")
        related_message.attach(alt_email_message)
        related_message.attach(inline_attachment)
        base_message = MIMEMultipart("mixed")
        base_message.attach(related_message)
        base_message.attach(email_as_attachment)
        utils.add_simple_email_headers(base_message, locale="en_US", use_short_email=True)
        # Now send the part to the email workflow
        extract_email_metadata(base_message.as_string(), self.queue_public, self.logger)

        self.assertEqual(len(mail.outbox), 1)  # @UndefinedVariable
        self.assertEqual(f'[test-1] {base_message.get("subject")} (Opened)', mail.outbox[0].subject)

        ticket = Ticket.objects.get()
        followup = ticket.followup_set.get()
        # Check both the inline and attachment are stored as attached files
        inline_found = False
        email_attachment_found = False
        for att_retrieved in followup.followupattachment_set.all():
            if (helpdesk.email.HTML_EMAIL_ATTACHMENT_FILENAME == att_retrieved.filename):
                # Ignore the HTML formatted content of the email that is attached 
                continue
            if att_retrieved.filename.endswith(inline_att_filename):
                inline_found = True
            elif  att_retrieved.filename.endswith(email_att_filename):
                email_attachment_found = True
            else:
                self.assertTrue(False, "Unexpected file in ticket attachments: %s" % att_retrieved.filename)
        self.assertTrue(email_attachment_found, "Email attachment file not found ticket attachments: %s" % (email_att_filename))
        self.assertTrue(inline_found, "Inline file not found in email: %s" % (inline_att_filename))

        
    def test_email_with_txt_as_attachment_with_simple_alternative_message(self):
        """
        Test an email with a txt extension email attachment to the email where the message part of the
        email is in a multipart/alternative directly off the main multipart/mixed (no multipart/related)
        """
        email_att_filename = 'the_quick_brown_fox.txt'
        # Create the actual email with its plain and HTML parts
        alt_email_message = MIMEMultipart("alternative")
        # Create the plain and HTML that will reference the inline attachment
        plain_body = "Is wet birds attached?\n\n"
        plain_msg = MIMEText(plain_body)
        alt_email_message.attach(plain_msg)
        html_body = '<div><div>Is wet birds attached?</div><br></div>'
        html_msg = MIMEText(html_body, "html")
        alt_email_message.attach(html_msg)
        # Now create the base multipart and attach all the other parts to it
        base_message = MIMEMultipart("mixed")
        base_message.attach(alt_email_message)
        email_attachment = MIMEText("Wet birds don't fly at night.")
        email_attachment.add_header('Content-Disposition', 'attachment', filename=email_att_filename)
        base_message.attach(email_attachment)
        utils.add_simple_email_headers(base_message, locale="en_US", use_short_email=True)
        # Now send the part to the email workflow
        extract_email_metadata(base_message.as_string(), self.queue_public, self.logger)
        self.assertEqual(len(mail.outbox), 1)  # @UndefinedVariable
        #self.assertEqual(f'[test-1] {base_message.get("subject")} (Opened)', mail.outbox[0].subject)

        ticket = Ticket.objects.get()
        followup = ticket.followup_set.get()
        # Check  attachment is stored as attached file
        email_attachment_found = False
        for att_retrieved in followup.followupattachment_set.all():
            if (helpdesk.email.HTML_EMAIL_ATTACHMENT_FILENAME == att_retrieved.filename):
                # Ignore the HTML formatted content of the email that is attached 
                continue
            if  att_retrieved.filename.endswith(email_att_filename):
                email_attachment_found = True
            else:
                self.assertTrue(False, "Unexpected file in ticket attachments: %s" % att_retrieved.filename)
        self.assertTrue(email_attachment_found, "Email attachment file not found ticket attachments: %s" % (email_att_filename))


class EmailTaskTests(TestCase):

    def setUp(self):
        self.num_queues = 5
        self.exception_queues = [2, 4]
        self.q_ids = []
        for i in range(self.num_queues):
            q = Queue.objects.create(
                    title=f'Test{i+1}',
                    slug=f'test{i+1}',
                    email_box_type='local',
                    allow_email_submission=True
                )
            self.q_ids.append(q.id)
        self.logger = logging.getLogger('helpdesk')

    def test_get_email_with_debug_to_stdout_option(self):
        """Test debug_to_stdout option """
        # Test get_email with debug_to_stdout set to True and also False, and verify
        # handle receives debug_to_stdout option set properly
        for debug_to_stdout in [True, False]:
            with mock.patch.object(Command, 'handle', return_value=None) as mocked_handle:
                call_command('get_email', "--debug_to_stdout") if debug_to_stdout else call_command('get_email')
                mocked_handle.assert_called_once()
                for _, kwargs in mocked_handle.call_args_list:
                    self.assertEqual(debug_to_stdout, (kwargs['debug_to_stdout']))

    @patch('helpdesk.email.process_queue')
    def test_get_email_with_queue_failure(self, mocked_process_queue):
        """Test all queues are processed if specified queues have exceptions"""
        ret_values = [
                Exception(f"Error Q{i};") if (i in self.exception_queues) else None for i in range(1, self.num_queues+1)
            ]
        mocked_process_queue.side_effect = ret_values
        call_command(
                'get_email',
                '--debug_to_stdout',
            )
        self.assertEqual(mocked_process_queue.call_count, self.num_queues)
        not_processed_count = Queue.objects.filter(
            email_box_type__isnull=False,
            allow_email_submission=True,
            email_box_last_check__isnull=True).count()
        self.assertEqual(
            not_processed_count,
            len(self.exception_queues),
            "Incorrect number of queues that did not get processed due to a forced exception."
            )


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

        self.token = {
            'token_type': 'Bearer',
            'access_token': 'asdfoiw37850234lkjsdfsdf',
            'refresh_token': 'sldvafkjw34509s8dfsdf',
            'expires_in': '3600',
            'expires_at': fake_time + 3600,
        }
        self.client_id = 'foo'
        self.client = BackendApplicationClient(self.client_id)


    def tearDown(self):

        rmtree(self.temp_logdir)

    def test_read_plain_email(self):
        """Tests reading plain text emails from a queue and creating tickets.
           For each email source supported, we mock the backend to provide
           authentically formatted responses containing our test data."""
        # example email text from Django docs:
        # https://docs.djangoproject.com/en/1.10/ref/unicode/
        test_email_from = "Arnbjörg Ráðormsdóttir <arnbjorg@example.com>"
        test_email_subject = "My visit to Sør-Trøndelag"
        test_email_body = "Unicode helpdesk comment with an s-hat (ŝ) via email."
        test_email = "To: helpdesk@example.com\nFrom: " + test_email_from + \
            "\nSubject: " + test_email_subject + "\n\n" + test_email_body
        test_mail_len = len(test_email)

        if self.socks:
            from socks import ProxyConnectionError
            with self.assertRaisesRegex(ProxyConnectionError, '%s:%s' % (unrouted_socks_server, unused_port)):
                call_command('get_email')

        else:
            # Test local email reading
            if self.method == 'local':
                with mock.patch('os.listdir') as mocked_listdir, \
                        mock.patch('helpdesk.email.isfile') as mocked_isfile, \
                        mock.patch('builtins.open', mock.mock_open(read_data=test_email)), \
                        mock.patch('os.unlink'):
                    mocked_isfile.return_value = True
                    mocked_listdir.return_value = ['filename1', 'filename2']

                    call_command('get_email')

                    mocked_listdir.assert_called_with(
                        '/var/lib/mail/helpdesk/')
                    mocked_isfile.assert_any_call(
                        '/var/lib/mail/helpdesk/filename1')
                    mocked_isfile.assert_any_call(
                        '/var/lib/mail/helpdesk/filename2')

            elif self.method == 'pop3':
                # mock poplib.POP3's list and retr methods to provide responses
                # as per RFC 1939
                pop3_emails = {
                    '1': ("+OK", test_email.split('\n')),
                    '2': ("+OK", test_email.split('\n')),
                }
                pop3_mail_list = ("+OK 2 messages", ("1 %d" %
                                                     test_mail_len, "2 %d" % test_mail_len))
                mocked_poplib_server = mock.Mock()
                mocked_poplib_server.list = mock.Mock(
                    return_value=pop3_mail_list)
                mocked_poplib_server.retr = mock.Mock(
                    side_effect=lambda x: pop3_emails[x])
                with mock.patch('helpdesk.email.poplib', autospec=True) as mocked_poplib:
                    mocked_poplib.POP3 = mock.Mock(
                        return_value=mocked_poplib_server)
                    call_command('get_email')

            elif self.method == 'imap':
                # mock imaplib.IMAP4's search and fetch methods with responses
                # from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", test_email),)),
                    "2": ("OK", (("2", test_email),)),
                }
                imap_mail_list = ("OK", ("1 2",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(
                    return_value=imap_mail_list)
                # we ignore the second arg as the data item/mime-part is
                # constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(
                    side_effect=lambda x, _: imap_emails[x])
                with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                    mocked_imaplib.IMAP4 = mock.Mock(
                        return_value=mocked_imaplib_server)
                    call_command('get_email')

            elif self.method == 'oauth':
                # mock the oauthlib session and requests oauth backendclient
                # then mock imaplib.IMAP4's search and fetch methods with responses
                # from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", test_email),)),
                    "2": ("OK", (("2", test_email),)),
                }
                imap_mail_list = ("OK", ("1 2",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(
                    return_value=imap_mail_list)
                # we ignore the second arg as the data item/mime-part is
                # constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(
                    side_effect=lambda x, _: imap_emails[x])

                mocked_oauth_backend_client = mock.Mock()
                with mock.patch('helpdesk.email.oauth2lib', autospec=True) as mocked_oauth2lib:
                    mocked_oauth2lib.BackendApplicationClient = mock.Mock(
                        return_value=mocked_oauth_backend_client)

                    mocked_oauth_session = mock.Mock()
                    mocked_oauth_session.fetch_token = mock.Mock(
                        return_value={}
                    )

                    with mock.patch('helpdesk.email.requests_oauthlib', autospec=True) as mocked_requests_oauthlib:
                        mocked_requests_oauthlib.OAuth2Session = mock.Mock(
                            return_value=mocked_oauth_session)

                        with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                            mocked_imaplib.IMAP4 = mock.Mock(
                                return_value=mocked_imaplib_server)

                            call_command('get_email')

            ticket1 = get_object_or_404(Ticket, pk=1)
            self.assertEqual(ticket1.ticket_for_url, "QQ-%s" % ticket1.id)
            self.assertEqual(ticket1.title, test_email_subject)
            self.assertEqual(ticket1.description, test_email_body)

            ticket2 = get_object_or_404(Ticket, pk=2)
            self.assertEqual(ticket2.ticket_for_url, "QQ-%s" % ticket2.id)
            self.assertEqual(ticket2.title, test_email_subject)
            self.assertEqual(ticket2.description, test_email_body)

    def test_commas_in_mail_headers(self):
        """Tests correctly decoding mail headers when a comma is encoded into
           UTF-8. See bug report #832."""
        # Create the from using standard RFC required formats
        # Override the last_name to ensure we get a non-ascii character in it
        test_email_from_meta = utils.generate_email_address("fr_FR", last_name_override="Bouissières")
        test_email_subject = "Commas in From lines"
        test_email_body = "Testing commas in from email UTF-8."
        test_email = "To: helpdesk@example.com\nFrom: " + test_email_from_meta[0] + \
            "\nSubject: " + test_email_subject + "\n\n" + test_email_body
        test_mail_len = len(test_email)

        if self.socks:
            from socks import ProxyConnectionError
            with self.assertRaisesRegex(ProxyConnectionError, '%s:%s' % (unrouted_socks_server, unused_port)):
                call_command('get_email')

        else:
            # Test local email reading
            if self.method == 'local':
                with mock.patch('os.listdir') as mocked_listdir, \
                        mock.patch('helpdesk.email.isfile') as mocked_isfile, \
                        mock.patch('builtins.open', mock.mock_open(read_data=test_email)), \
                        mock.patch('os.unlink'):
                    mocked_isfile.return_value = True
                    mocked_listdir.return_value = ['filename1', 'filename2']

                    call_command('get_email')

                    mocked_listdir.assert_called_with(
                        '/var/lib/mail/helpdesk/')
                    mocked_isfile.assert_any_call(
                        '/var/lib/mail/helpdesk/filename1')
                    mocked_isfile.assert_any_call(
                        '/var/lib/mail/helpdesk/filename2')

            elif self.method == 'pop3':
                # mock poplib.POP3's list and retr methods to provide responses
                # as per RFC 1939
                pop3_emails = {
                    '1': ("+OK", test_email.split('\n')),
                    '2': ("+OK", test_email.split('\n')),
                }
                pop3_mail_list = ("+OK 2 messages", ("1 %d" %
                                                     test_mail_len, "2 %d" % test_mail_len))
                mocked_poplib_server = mock.Mock()
                mocked_poplib_server.list = mock.Mock(
                    return_value=pop3_mail_list)
                mocked_poplib_server.retr = mock.Mock(
                    side_effect=lambda x: pop3_emails[x])
                with mock.patch('helpdesk.email.poplib', autospec=True) as mocked_poplib:
                    mocked_poplib.POP3 = mock.Mock(
                        return_value=mocked_poplib_server)
                    call_command('get_email')

            elif self.method == 'imap':
                # mock imaplib.IMAP4's search and fetch methods with responses
                # from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", test_email),)),
                    "2": ("OK", (("2", test_email),)),
                }
                imap_mail_list = ("OK", ("1 2",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(
                    return_value=imap_mail_list)
                # we ignore the second arg as the data item/mime-part is
                # constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(
                    side_effect=lambda x, _: imap_emails[x])
                with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                    mocked_imaplib.IMAP4 = mock.Mock(
                        return_value=mocked_imaplib_server)
                    call_command('get_email')

            elif self.method == 'oauth':
                # mock the oauthlib session and requests oauth backendclient
                # then mock imaplib.IMAP4's search and fetch methods with responses
                # from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", test_email),)),
                    "2": ("OK", (("2", test_email),)),
                }
                imap_mail_list = ("OK", ("1 2",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(
                    return_value=imap_mail_list)
                # we ignore the second arg as the data item/mime-part is
                # constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(
                    side_effect=lambda x, _: imap_emails[x])

                mocked_oauth_backend_client = mock.Mock()
                with mock.patch('helpdesk.email.oauth2lib', autospec=True) as mocked_oauth2lib:
                    mocked_oauth2lib.BackendApplicationClient = mock.Mock(
                        return_value=mocked_oauth_backend_client)

                    mocked_oauth_session = mock.Mock()
                    mocked_oauth_session.fetch_token = mock.Mock(
                        return_value={}
                    )

                    with mock.patch('helpdesk.email.requests_oauthlib', autospec=True) as mocked_requests_oauthlib:
                        mocked_requests_oauthlib.OAuth2Session = mock.Mock(
                            return_value=mocked_oauth_session)

                        with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                            mocked_imaplib.IMAP4 = mock.Mock(
                                return_value=mocked_imaplib_server)

                            call_command('get_email')

            ticket1 = get_object_or_404(Ticket, pk=1)
            self.assertEqual(ticket1.ticket_for_url, "QQ-%s" % ticket1.id)
            self.assertEqual(ticket1.submitter_email, test_email_from_meta[1])
            self.assertEqual(ticket1.title, test_email_subject)
            self.assertEqual(ticket1.description, test_email_body)

            ticket2 = get_object_or_404(Ticket, pk=2)
            self.assertEqual(ticket2.ticket_for_url, "QQ-%s" % ticket2.id)
            self.assertEqual(ticket2.submitter_email, test_email_from_meta[1])
            self.assertEqual(ticket2.title, test_email_subject)
            self.assertEqual(ticket2.description, test_email_body)

    def test_read_email_with_template_tag(self):
        """Tests reading plain text emails from a queue and creating tickets,
           except this time the email body contains a Django template tag.
           For each email source supported, we mock the backend to provide
           authentically formatted responses containing our test data."""
        # example email text from Django docs:
        # https://docs.djangoproject.com/en/1.10/ref/unicode/
        test_email_from = "Arnbjörg Ráðormsdóttir <arnbjorg@example.com>"
        test_email_subject = "My visit to Sør-Trøndelag"
        test_email_body = "Reporting some issue with the template tag: {% if helpdesk %}."
        test_email = "To: helpdesk@example.com\nFrom: " + test_email_from + \
            "\nSubject: " + test_email_subject + "\n\n" + test_email_body
        test_mail_len = len(test_email)

        if self.socks:
            from socks import ProxyConnectionError
            with self.assertRaisesRegex(ProxyConnectionError, '%s:%s' % (unrouted_socks_server, unused_port)):
                call_command('get_email')

        else:
            # Test local email reading
            if self.method == 'local':
                with mock.patch('os.listdir') as mocked_listdir, \
                        mock.patch('helpdesk.email.isfile') as mocked_isfile, \
                        mock.patch('builtins.open', mock.mock_open(read_data=test_email)), \
                        mock.patch('os.unlink'):
                    mocked_isfile.return_value = True
                    mocked_listdir.return_value = ['filename1', 'filename2']

                    call_command('get_email')

                    mocked_listdir.assert_called_with(
                        '/var/lib/mail/helpdesk/')
                    mocked_isfile.assert_any_call(
                        '/var/lib/mail/helpdesk/filename1')
                    mocked_isfile.assert_any_call(
                        '/var/lib/mail/helpdesk/filename2')

            elif self.method == 'pop3':
                # mock poplib.POP3's list and retr methods to provide responses
                # as per RFC 1939
                pop3_emails = {
                    '1': ("+OK", test_email.split('\n')),
                    '2': ("+OK", test_email.split('\n')),
                }
                pop3_mail_list = ("+OK 2 messages", ("1 %d" %
                                                     test_mail_len, "2 %d" % test_mail_len))
                mocked_poplib_server = mock.Mock()
                mocked_poplib_server.list = mock.Mock(
                    return_value=pop3_mail_list)
                mocked_poplib_server.retr = mock.Mock(
                    side_effect=lambda x: pop3_emails[x])
                with mock.patch('helpdesk.email.poplib', autospec=True) as mocked_poplib:
                    mocked_poplib.POP3 = mock.Mock(
                        return_value=mocked_poplib_server)
                    call_command('get_email')

            elif self.method == 'imap':
                # mock imaplib.IMAP4's search and fetch methods with responses
                # from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", test_email),)),
                    "2": ("OK", (("2", test_email),)),
                }
                imap_mail_list = ("OK", ("1 2",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(
                    return_value=imap_mail_list)
                # we ignore the second arg as the data item/mime-part is
                # constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(
                    side_effect=lambda x, _: imap_emails[x])
                with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                    mocked_imaplib.IMAP4 = mock.Mock(
                        return_value=mocked_imaplib_server)
                    call_command('get_email')

            elif self.method == 'oauth':
                # mock the oauthlib session and requests oauth backendclient
                # then mock imaplib.IMAP4's search and fetch methods with responses
                # from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", test_email),)),
                    "2": ("OK", (("2", test_email),)),
                }
                imap_mail_list = ("OK", ("1 2",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(
                    return_value=imap_mail_list)
                # we ignore the second arg as the data item/mime-part is
                # constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(
                    side_effect=lambda x, _: imap_emails[x])

                mocked_oauth_backend_client = mock.Mock()
                with mock.patch('helpdesk.email.oauth2lib', autospec=True) as mocked_oauth2lib:
                    mocked_oauth2lib.BackendApplicationClient = mock.Mock(
                        return_value=mocked_oauth_backend_client)

                    mocked_oauth_session = mock.Mock()
                    mocked_oauth_session.fetch_token = mock.Mock(
                        return_value={}
                    )

                    with mock.patch('helpdesk.email.requests_oauthlib', autospec=True) as mocked_requests_oauthlib:
                        mocked_requests_oauthlib.OAuth2Session = mock.Mock(
                            return_value=mocked_oauth_session)

                        with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                            mocked_imaplib.IMAP4 = mock.Mock(
                                return_value=mocked_imaplib_server)

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
        # example email text from Python docs:
        # https://docs.python.org/3/library/email-examples.html
        me = "my@example.com"
        you = "your@example.com"
        # NOTE: CC'd emails need to be alphabetical and tested as such!
        # implementation uses sets, so only way to ensure tickets created
        # in right order is to change set to list and sort it
        cc_one = "nobody@example.com"
        cc_two = "other@example.com"
        cc = cc_one + ", " + cc_two
        subject = "Link"
        # Create message container - the correct MIME type is
        # multipart/alternative.
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
                with mock.patch('os.listdir') as mocked_listdir, \
                        mock.patch('helpdesk.email.isfile') as mocked_isfile, \
                        mock.patch('builtins.open', mock.mock_open(read_data=msg.as_string())), \
                        mock.patch('os.unlink'):
                    mocked_isfile.return_value = True
                    mocked_listdir.return_value = ['filename1', 'filename2']

                    call_command('get_email')

                    mocked_listdir.assert_called_with(
                        '/var/lib/mail/helpdesk/')
                    mocked_isfile.assert_any_call(
                        '/var/lib/mail/helpdesk/filename1')
                    mocked_isfile.assert_any_call(
                        '/var/lib/mail/helpdesk/filename2')

            elif self.method == 'pop3':
                # mock poplib.POP3's list and retr methods to provide responses
                # as per RFC 1939
                pop3_emails = {
                    '1': ("+OK", msg.as_string().split('\n')),
                    '2': ("+OK", msg.as_string().split('\n')),
                }
                pop3_mail_list = ("+OK 2 messages", ("1 %d" %
                                                     test_mail_len, "2 %d" % test_mail_len))
                mocked_poplib_server = mock.Mock()
                mocked_poplib_server.list = mock.Mock(
                    return_value=pop3_mail_list)
                mocked_poplib_server.retr = mock.Mock(
                    side_effect=lambda x: pop3_emails[x])
                with mock.patch('helpdesk.email.poplib', autospec=True) as mocked_poplib:
                    mocked_poplib.POP3 = mock.Mock(
                        return_value=mocked_poplib_server)
                    call_command('get_email')


            elif self.method == 'imap':
                # mock imaplib.IMAP4's search and fetch methods with responses
                # from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", msg.as_string()),)),
                    "2": ("OK", (("2", msg.as_string()),)),
                }
                imap_mail_list = ("OK", ("1 2",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(
                    return_value=imap_mail_list)
                # we ignore the second arg as the data item/mime-part is
                # constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(
                    side_effect=lambda x, _: imap_emails[x])
                with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                    mocked_imaplib.IMAP4 = mock.Mock(
                        return_value=mocked_imaplib_server)
                    call_command('get_email')

            elif self.method == 'oauth':
                # mock the oauthlib session and requests oauth backendclient
                # then mock imaplib.IMAP4's search and fetch methods with responses
                # from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", msg.as_string()),)),
                    "2": ("OK", (("2", msg.as_string()),)),
                }
                imap_mail_list = ("OK", ("1 2",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(
                    return_value=imap_mail_list)
                # we ignore the second arg as the data item/mime-part is
                # constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(
                    side_effect=lambda x, _: imap_emails[x])

                mocked_oauth_backend_client = mock.Mock()
                with mock.patch('helpdesk.email.oauth2lib', autospec=True) as mocked_oauth2lib:
                    mocked_oauth2lib.BackendApplicationClient = mock.Mock(
                        return_value=mocked_oauth_backend_client)

                    mocked_oauth_session = mock.Mock()
                    mocked_oauth_session.fetch_token = mock.Mock(
                        return_value={}
                    )

                    with mock.patch('helpdesk.email.requests_oauthlib', autospec=True) as mocked_requests_oauthlib:
                        mocked_requests_oauthlib.OAuth2Session = mock.Mock(
                            return_value=mocked_oauth_session)

                        with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                            mocked_imaplib.IMAP4 = mock.Mock(
                                return_value=mocked_imaplib_server)

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
        with open(os.path.join(THIS_DIR, "test_files/pgp.eml"), encoding="utf-8") as fd:
            test_email = fd.read()
        test_mail_len = len(test_email)

        if self.socks:
            from socks import ProxyConnectionError
            with self.assertRaisesRegex(ProxyConnectionError, '%s:%s' % (unrouted_socks_server, unused_port)):
                call_command('get_email')

        else:
            # Test local email reading
            if self.method == 'local':
                with mock.patch('os.listdir') as mocked_listdir, \
                        mock.patch('helpdesk.email.isfile') as mocked_isfile, \
                        mock.patch('builtins.open', mock.mock_open(read_data=test_email)), \
                        mock.patch('os.unlink'):
                    mocked_isfile.return_value = True
                    mocked_listdir.return_value = ['filename1']

                    call_command('get_email')

                    mocked_listdir.assert_called_with(
                        '/var/lib/mail/helpdesk/')
                    mocked_isfile.assert_any_call(
                        '/var/lib/mail/helpdesk/filename1')

            elif self.method == 'pop3':
                # mock poplib.POP3's list and retr methods to provide responses
                # as per RFC 1939
                pop3_emails = {
                    '1': ("+OK", test_email.split('\n')),
                }
                pop3_mail_list = ("+OK 1 message", ("1 %d" % test_mail_len))
                mocked_poplib_server = mock.Mock()
                mocked_poplib_server.list = mock.Mock(
                    return_value=pop3_mail_list)
                mocked_poplib_server.retr = mock.Mock(
                    side_effect=lambda x: pop3_emails['1'])
                with mock.patch('helpdesk.email.poplib', autospec=True) as mocked_poplib:
                    mocked_poplib.POP3 = mock.Mock(
                        return_value=mocked_poplib_server)
                    call_command('get_email')


            elif self.method == 'imap':
                # mock imaplib.IMAP4's search and fetch methods with responses
                # from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", test_email),)),
                }
                imap_mail_list = ("OK", ("1",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(
                    return_value=imap_mail_list)
                # we ignore the second arg as the data item/mime-part is
                # constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(
                    side_effect=lambda x, _: imap_emails[x])
                with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                    mocked_imaplib.IMAP4 = mock.Mock(
                        return_value=mocked_imaplib_server)
                    call_command('get_email')

            elif self.method == 'oauth':
                # mock the oauthlib session and requests oauth backendclient
                # then mock imaplib.IMAP4's search and fetch methods with responses
                # from RFC 3501
                imap_emails = {
                    "1": ("OK", (("1", test_email),)),
                }
                imap_mail_list = ("OK", ("1",))
                mocked_imaplib_server = mock.Mock()
                mocked_imaplib_server.search = mock.Mock(
                    return_value=imap_mail_list)
                # we ignore the second arg as the data item/mime-part is
                # constant (RFC822)
                mocked_imaplib_server.fetch = mock.Mock(
                    side_effect=lambda x, _: imap_emails[x])

                mocked_oauth_backend_client = mock.Mock()
                with mock.patch('helpdesk.email.oauth2lib', autospec=True) as mocked_oauth2lib:
                    mocked_oauth2lib.BackendApplicationClient = mock.Mock(
                        return_value=mocked_oauth_backend_client)

                    mocked_oauth_session = mock.Mock()
                    mocked_oauth_session.fetch_token = mock.Mock(
                        return_value={}
                    )

                    with mock.patch('helpdesk.email.requests_oauthlib', autospec=True) as mocked_requests_oauthlib:
                        mocked_requests_oauthlib.OAuth2Session = mock.Mock(
                            return_value=mocked_oauth_session)

                        with mock.patch('helpdesk.email.imaplib', autospec=True) as mocked_imaplib:
                            mocked_imaplib.IMAP4 = mock.Mock(
                                return_value=mocked_imaplib_server)

                            call_command('get_email')

            ticket1 = get_object_or_404(Ticket, pk=1)
            self.assertEqual(ticket1.ticket_for_url, "QQ-%s" % ticket1.id)
            self.assertEqual(
                ticket1.title, "example email that crashes django-helpdesk get_email")
            self.assertEqual(
                ticket1.description, """hi, thanks for looking into this :)\n\nhttps://github.com/django-helpdesk/django-helpdesk/issues/567#issuecomment-342954233""")
            # MIME part should be attached to follow up
            followup1 = get_object_or_404(FollowUp, pk=1)
            self.assertEqual(followup1.ticket.id, 1)
            attach1 = get_object_or_404(FollowUpAttachment, pk=1)
            self.assertEqual(attach1.followup.id, 1)
            self.assertEqual(attach1.filename, 'part-1_signature.asc')
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
        self.assertEqual(ticket1.assigned_to,
                         User.objects.get(username='assigned'))
        # example email text from Django docs:
        # https://docs.djangoproject.com/en/1.10/ref/unicode/
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
        test_email = "To: queue@example.com\nCc: " + test_email_cc_one + ", " + test_email_cc_one + ", " + test_email_cc_two + ", " + test_email_cc_three + "\nCC: " + test_email_cc_one + \
            ", " + test_email_cc_three + ", " + test_email_cc_four + ", " + ticket_user_emails + \
            "\nFrom: " + test_email_from + "\nSubject: " + \
            test_email_subject + "\n\n" + test_email_body

        with mock.patch('os.listdir') as mocked_listdir, \
                mock.patch('helpdesk.email.isfile') as mocked_isfile, \
                mock.patch('builtins.open', mock.mock_open(read_data=test_email)), \
                mock.patch('os.unlink'):
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
# uncomment if you want to run tests with socks - which is much slover
# case_socks = [False] + [c[0] for c in Queue._meta.get_field('socks_proxy_type').choices]
case_socks = [False]
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

    cl = type(test_name, (GetEmailParametricTemplate, TestCase),
              {"method": method, "socks": socks})
    setattr(thismodule, test_name, cl)
