# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from helpdesk.models import Queue, Ticket, TicketCC, FollowUp, Attachment
from django.test import TestCase
from django.core.management import call_command
from django.utils import six
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
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
            cc1 = get_object_or_404(TicketCC, pk=1)
            self.assertEqual(cc1.email, cc_one)
            cc2 = get_object_or_404(TicketCC, pk=2)
            self.assertEqual(cc2.email, cc_two)
            self.assertEqual(len(TicketCC.objects.filter(ticket=1)), 2)

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

    def test_read_pgp_signed_email(self):
        """Tests reading a PGP signed email to ensure we handle base64
           and PGP signatures appropriately."""

        # example email text from #567 on GitHub
        test_email = """Delivered-To: djangohelpdesk@example.com
Received: by 10.25.26.207 with SMTP id a198csp5858981lfa;
        Wed, 8 Nov 2017 13:30:22 -0800 (PST)
X-Received: by 10.107.107.3 with SMTP id g3mr2603398ioc.250.1510176622046;
        Wed, 08 Nov 2017 13:30:22 -0800 (PST)
ARC-Seal: i=2; a=rsa-sha256; t=1510176621; cv=pass;
        d=google.com; s=arc-20160816;
        b=qQ8kBj8+yIoWcJwFNHUlJDYz7P2NfILAxFsn9uPYzXNn/aRw695T1aNFgGL75KUhkA
         nDw+h49SUGKDh9ehC+DEiPjwJIxAoz+86rqGWV6XPGW4gQ7GUkHs96CxWndTSD0hdcOl
         vygeZrsgzpIOvDxJWrujDPZzcEjsPC2qy3KGsTqtbZGEsNhhRUD8rs/hBVVXaGBatLF+
         Sz2krwBZz8Lm+mWRhScjmF12QIHcXe6qYrDLOLEK0+bRkRMS+ZXg9+GPwqHlp58GaHn+
         6JncesW3q7k88RQsLlj/8PEw0z1wMndgBVWIcCEtLt4UhZtt/BDxmZSukNN0SzoH4e3k
         mxOw==
ARC-Message-Signature: i=2; a=rsa-sha256; c=relaxed/relaxed; d=google.com; s=arc-20160816;
        h=mime-version:user-agent:date:message-id:subject:from:to
         :dkim-signature:arc-authentication-results:arc-message-signature
         :arc-authentication-results;
        bh=cQvDBdivwtDmp1Td9ZWaEf0S4IuZ4hPwaprxSv7XZuE=;
        b=p/0Y4PgvEfGWZ8W3eqxzRnSGLbT9gObSU2OI/sLwiN4KFfVmGrBJYkx7DGija0A5eU
         DBbETW/16pib+W0IOUtdD7Pt12oWA3Z/uRf7ybXnHIKZ+MObdCXqRJFkga6nY8tWD0H3
         maquQR07Q54mYslVMEIKJUKJzVM86npLN2C756ZzZTXiGXf33iowO4/lciGmTAgi+y5p
         fEDQCTMoSQ9iGbquFRgNHgMtIM5NWjeMksWKpnfbvZyKs0ZICcPklNxQkDCmDlrOBokT
         Zs1RVsWZ7NyPdTomJ0SRyPeysM040aatmnwxFAzwe4GYFNUWZjaep7uPKKlZ4sV/aHBB
         iHOQ==
ARC-Authentication-Results: i=2; mx.google.com;
       dkim=pass header.i=@gmail.com header.s=20161025 header.b=AArzbi/1;
       arc=pass (i=1 spf=pass spfdomain=gmail.com dkim=pass dkdomain=gmail.com dmarc=pass fromdomain=gmail.com);
       spf=pass (google.com: domain of bugreporter@example.com designates 209.85.220.41 as permitted sender) smtp.mailfrom=bugreporter@example.com;
       dmarc=pass (p=NONE sp=NONE dis=NONE) header.from=gmail.com
Return-Path: <bugreporter@example.com>
Received: from mail-sor-f41.google.com (mail-sor-f41.google.com. [209.85.220.41])
        by mx.google.com with SMTPS id i86sor2420323ioo.204.2017.11.08.13.30.21
        for <djangohelpdesk@example.com>
        (Google Transport Security);
        Wed, 08 Nov 2017 13:30:21 -0800 (PST)
Received-SPF: pass (google.com: domain of bugreporter@example.com designates 209.85.220.41 as permitted sender) client-ip=209.85.220.41;
Authentication-Results: mx.google.com;
       dkim=pass header.i=@gmail.com header.s=20161025 header.b=AArzbi/1;
       arc=pass (i=1 spf=pass spfdomain=gmail.com dkim=pass dkdomain=gmail.com dmarc=pass fromdomain=gmail.com);
       spf=pass (google.com: domain of bugreporter@example.com designates 209.85.220.41 as permitted sender) smtp.mailfrom=bugreporter@example.com;
       dmarc=pass (p=NONE sp=NONE dis=NONE) header.from=gmail.com
X-Google-DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed;
        d=1e100.net; s=20161025;
        h=x-gm-message-state:dkim-signature:to:from:subject:message-id:date
         :user-agent:mime-version;
        bh=cQvDBdivwtDmp1Td9ZWaEf0S4IuZ4hPwaprxSv7XZuE=;
        b=MCiZzHu6ZV3kMTQBRL/b5uBy4jbHFS97+z9apL239dYS+z0LlTiHpKbs3qohFe3As1
         gu2l0SAcdGw0qeplgmOlX9HXvKetBRLldfHeX/JJZ2yokpjc6CxVT8gF8YP2UmfAs0cb
         JI8TTDqiWmhayf7xfblRIUP7vfwyTH9cLmvKMMAqWvrppyUlqlxWgyO7xtzV9jdThpqP
         O0jO9CqsRmbEDc4vZAtOTXm1O69jCz66oll6H4T5Nka9HUpyHFZzv7Z0j0F/5djfzjCQ
         HCFZhzobEgZAmBC9o2Y5aDvKCnWJGR5kVTtBQaFCuxr57o4zq0D359V3gMMPRGMdujDP
         hXAQ==
X-Google-Smtp-Source: ABhQp+SbAIRuabSw2EkD+7YFXtLiCFINtymAshxVYuNZhApd39ymv2m9UnIM3rZNIHonQBywtZ3VjalQxeN8lVuWD6OquEskEc8=
ARC-Seal: i=1; a=rsa-sha256; t=1510176621; cv=none;
        d=google.com; s=arc-20160816;
        b=mOqnqVV4oq14hoOdEA+yVvQYQd/sv/Qr//xmW6r94dKaUczdbFG+Uy8x7EbuF/ILJt
         ByFmE8+HUH8tosfHn8+zFmsHFr3Wi7il64wdeuVqoOuDQS1HejcH9ln5LVjwsr7EE6Ly
         6gCT7QupvSQ+FkhyNH+zNHuGztw5F4Sa2r5UlmR5VAJ4+V1MEfVYwzEr7vgPnmEj8jga
         PtmD05EfYWrWt27Cw8oS+CgS0CNcHaaiRr7JX3EQbNRrLp5M9GjKhiq/ckt2a5NKJYMH
         zISYQzxk7EgHGFrwn+JZx+oKqG3Zl2pd5oKmzJkFeSaGT+qYp3SES4z3Vi6z4VxGduox
         f38g==
ARC-Message-Signature: i=1; a=rsa-sha256; c=relaxed/relaxed; d=google.com; s=arc-20160816;
        h=mime-version:user-agent:date:message-id:subject:from:to
         :dkim-signature:arc-authentication-results;
        bh=cQvDBdivwtDmp1Td9ZWaEf0S4IuZ4hPwaprxSv7XZuE=;
        b=R5FsED2qOoEJshMotswEPOAn8GyvaHHd4zM9wAH+qnzuoV9RFhSChbkAkypi73SPs/
         D7K49dYKSfsuWPF1RXoD8qchVfROF5Y7kD0JHy7KJcuHXzwb5gYLNrZpB2R9XbBOGe1j
         lgQvnEVwmgeJiLXKQVeQDECxs8DFlkIpPIbmJK02Ry/Q0S8TnBEs0mrWn49l70IsZB6U
         0XCpUPAt9NhsIUxoZKZv+zOwpQq6uwJkqRa5ukH0OPRr891MpeZldw7+gINjxxEmPAS9
         GYfMeCpX9afFbQMUizbUbKwOZPt7ahn3x1C5x4AwgQmtzXYfA/quyiXAukTzoYk8FUqs
         U1QA==
ARC-Authentication-Results: i=1; gmr-mx.google.com;
       dkim=pass header.i=@gmail.com header.s=20161025 header.b=AArzbi/1;
       spf=pass (google.com: domain of bugreporter@example.com designates 2607:f8b0:400e:c00::233 as permitted sender) smtp.mailfrom=bugreporter@example.com;
       dmarc=pass (p=NONE sp=NONE dis=NONE) header.from=gmail.com
Return-Path: <bugreporter@example.com>
Received: from mail-pf0-x233.google.com (mail-pf0-x233.google.com. [2607:f8b0:400e:c00::233])
        by gmr-mx.google.com with ESMTPS id l10si463482ioc.2.2017.11.08.13.30.21
        for <djangohelpdesk@example.com>
        (version=TLS1_2 cipher=ECDHE-RSA-AES128-GCM-SHA256 bits=128/128);
        Wed, 08 Nov 2017 13:30:21 -0800 (PST)
Received-SPF: pass (google.com: domain of bugreporter@example.com designates 2607:f8b0:400e:c00::233 as permitted sender) client-ip=2607:f8b0:400e:c00::233;
Received: by mail-pf0-x233.google.com with SMTP id p87so2672006pfj.3
        for <djangohelpdesk@example.com>; Wed, 08 Nov 2017 13:30:21 -0800 (PST)
DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed;
        d=gmail.com; s=20161025;
        h=to:from:subject:message-id:date:user-agent:mime-version;
        bh=cQvDBdivwtDmp1Td9ZWaEf0S4IuZ4hPwaprxSv7XZuE=;
        b=AArzbi/1RXhgTnCQBzU6vCwndc0/vqLV9FCgiOTp3deq8kFYhtdJCaEBX9s7iJduV+
         HobvLGsbmWU04Y1O3w8m4jyq5H4HJ1jAr1+i0Tf5jl264kmyu4eowOMkwIFo6UaSVQ/a
         zP+EYW09fWSSNhljubLkGf62vZ9gD/RF5Awoady6u5/N1GU4GPVCEgsmiK7DmPB2EtSE
         7YPz3o9l+kDy8bRnUFw0744B7VKiXrAcIqpfltJuItM4T7bS/jyjYMQbRn8W2MXpyGlI
         LNwt3vUNdKtkcPTK54cs44HMaVA8wGCDaMHFP8JmoTKWSsOgZQja3cdEj/rooM8uz+dq
         er5g==
X-Received: by 10.99.191.78 with SMTP id i14mr1746749pgo.220.1510176620834;
        Wed, 08 Nov 2017 13:30:20 -0800 (PST)
Return-Path: <bugreporter@example.com>
Received: from [10.1.1.4] (d114-72-199-247.hum1.act.optusnet.com.au. [114.72.199.247])
        by smtp.gmail.com with ESMTPSA id u131sm8656745pgc.89.2017.11.08.13.30.18
        for <djangohelpdesk@example.com>
        (version=TLS1_2 cipher=ECDHE-RSA-AES128-GCM-SHA256 bits=128/128);
        Wed, 08 Nov 2017 13:30:19 -0800 (PST)
To: djangohelpdesk@example.com
From: Bug Reporter <bugreporter@example.com>
Subject: example email that crashes django-helpdesk get_email
Message-ID: <8eef2077-8aff-9fb4-0e2a-9876ba2530b1@gmail.com>
Date: Thu, 9 Nov 2017 08:30:15 +1100
User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:52.0) Gecko/20100101
 Thunderbird/52.4.0
MIME-Version: 1.0
Content-Type: multipart/signed; micalg=pgp-sha256;
 protocol="application/pgp-signature";
 boundary="vnaePdRl5oElllhQPTiU2WarPFVGINT69"

This is an OpenPGP/MIME signed message (RFC 4880 and 3156)
--vnaePdRl5oElllhQPTiU2WarPFVGINT69
Content-Type: multipart/mixed; boundary="ckOQ1U5bPjO3W1sVnjdBaEigXBiwem2Rn";
 protected-headers="v1"
From: Bug Reporter <bugreporter@example.com>
To: djangohelpdesk@example.com
Message-ID: <8eef2077-8aff-9fb4-0e2a-9876ba2530b1@gmail.com>
Subject: example email that crashes django-helpdesk get_email

--ckOQ1U5bPjO3W1sVnjdBaEigXBiwem2Rn
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: quoted-printable
Content-Language: en-US

hi, thanks for looking into this :)

https://github.com/django-helpdesk/django-helpdesk/issues/567#issuecommen=
t-342954233


--ckOQ1U5bPjO3W1sVnjdBaEigXBiwem2Rn--

--vnaePdRl5oElllhQPTiU2WarPFVGINT69
Content-Type: application/pgp-signature; name="signature.asc"
Content-Description: OpenPGP digital signature
Content-Disposition: attachment; filename="signature.asc"

-----BEGIN PGP SIGNATURE-----

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

--vnaePdRl5oElllhQPTiU2WarPFVGINT69--

"""
        test_mail_len = len(test_email)

        if self.socks:
            from socks import ProxyConnectionError
            with self.assertRaisesRegex(ProxyConnectionError, '%s:%s' % (unrouted_socks_server, unused_port)):
                call_command('get_email')

        else:
            # Test local email reading
            if self.method == 'local':
                with mock.patch('helpdesk.management.commands.get_email.listdir') as mocked_listdir, \
                        mock.patch('helpdesk.management.commands.get_email.isfile') as mocked_isfile, \
                        mock.patch('builtins.open' if six.PY3 else '__builtin__.open', mock.mock_open(read_data=test_email)):
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
                with mock.patch('helpdesk.management.commands.get_email.poplib', autospec=True) as mocked_poplib:
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
                with mock.patch('helpdesk.management.commands.get_email.imaplib', autospec=True) as mocked_imaplib:
                    mocked_imaplib.IMAP4 = mock.Mock(return_value=mocked_imaplib_server)
                    call_command('get_email')

            ticket1 = get_object_or_404(Ticket, pk=1)
            self.assertEqual(ticket1.ticket_for_url, "QQ-%s" % ticket1.id)
            self.assertEqual(ticket1.title, "example email that crashes django-helpdesk get_email")
            self.assertEqual(ticket1.description, """hi, thanks for looking into this :)\n\nhttps://github.com/django-helpdesk/django-helpdesk/issues/567#issuecomment-342954233""")
            # MIME part should be attached to follow up
            followup1 = get_object_or_404(FollowUp, pk=1)
            self.assertEqual(followup1.ticket.id, 1)
            attach1 = get_object_or_404(Attachment, pk=1)
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

        with mock.patch('helpdesk.management.commands.get_email.listdir') as mocked_listdir, \
                mock.patch('helpdesk.management.commands.get_email.isfile') as mocked_isfile, \
                mock.patch('builtins.open' if six.PY3 else '__builtin__.open', mock.mock_open(read_data=test_email)):

            mocked_isfile.return_value = True
            mocked_listdir.return_value = ['filename1']

            call_command('get_email')

            mocked_listdir.assert_called_with('/var/lib/mail/helpdesk/')
            mocked_isfile.assert_any_call('/var/lib/mail/helpdesk/filename1')

        # ensure these 4 CCs (test_email_cc one thru four) are the only ones
        # created and added to the existing staff_user that was CC'd,
        # and the observer user that gets CC'd to new email.,
        # and that submitter and assignee are not added as CC either
        # (in other words, even though everyone was CC'd to this email,
        #  we should come out with only 6 CCs after filtering)
        self.assertEqual(len(TicketCC.objects.filter(ticket=1)), 6)
        # next we make sure no duplicates were added, and the
        # staff users nor submitter were not re-added as email TicketCCs
        cc0 = get_object_or_404(TicketCC, pk=2)
        self.assertEqual(cc0.user, User.objects.get(username='observer'))
        cc1 = get_object_or_404(TicketCC, pk=3)
        self.assertEqual(cc1.email, test_email_cc_one)
        cc2 = get_object_or_404(TicketCC, pk=4)
        self.assertEqual(cc2.email, test_email_cc_two)
        cc3 = get_object_or_404(TicketCC, pk=5)
        self.assertEqual(cc3.email, test_email_cc_three)
        cc4 = get_object_or_404(TicketCC, pk=6)
        self.assertEqual(cc4.email, test_email_cc_four)


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
