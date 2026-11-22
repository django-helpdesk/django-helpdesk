import logging
import os
from datetime import timedelta
from unittest import mock

from django.test import SimpleTestCase
from django.utils import timezone

from helpdesk.email import pop3_sync


class POP3ErrorHandlingTests(SimpleTestCase):
    def test_starttls_failure_continues_processing(self):
        queue = mock.Mock()
        queue.email_box_user = "user@example.com"
        queue.email_box_pass = "password"
        logger = mock.Mock(spec=logging.Logger)
        server = mock.Mock()
        server.stls.side_effect = RuntimeError("STARTTLS unavailable")
        server.list.return_value = ("+OK", [])

        pop3_sync(queue, logger, server)

        logger.warning.assert_called_once_with(
            "POP3 StartTLS failed or unsupported. Connection will be unencrypted."
        )
        server.user.assert_called_once_with("user@example.com")
        server.pass_.assert_called_once_with("password")
        server.quit.assert_called_once_with()

    @mock.patch("helpdesk.email.oauth2lib.BackendApplicationClient")
    @mock.patch("helpdesk.email.requests_oauthlib.OAuth2Session")
    def test_oauth_authentication_failure_logs_out(self, mocked_session, mocked_client):
        import imaplib

        from helpdesk.email import imap_oauth_sync

        queue = mock.Mock()
        queue.email_box_user = "user@example.com"
        queue.email_box_imap_folder = "INBOX"
        logger = mock.Mock(spec=logging.Logger)
        server = mock.Mock()
        server.authenticate.side_effect = imaplib.IMAP4.abort("Authentication failed")
        mocked_session.return_value.fetch_token.return_value = {
            "access_token": "test-token"
        }

        with self.assertRaises(SystemExit):
            imap_oauth_sync(queue, logger, server)

        logger.exception.assert_called_once_with("IMAP authentication failed in OAUTH")
        server.logout.assert_called_once_with()

    @mock.patch("helpdesk.email.oauth2lib.BackendApplicationClient")
    @mock.patch("helpdesk.email.requests_oauthlib.OAuth2Session")
    def test_oauth_ssl_failure_logs_out(self, mocked_session, mocked_client):
        import ssl

        from helpdesk.email import imap_oauth_sync

        queue = mock.Mock()
        queue.email_box_user = "user@example.com"
        queue.email_box_imap_folder = "INBOX"
        logger = mock.Mock(spec=logging.Logger)
        server = mock.Mock()
        server.authenticate.side_effect = ssl.SSLError("SSL connection failed")
        mocked_session.return_value.fetch_token.return_value = {
            "access_token": "test-token"
        }

        with self.assertRaises(SystemExit):
            imap_oauth_sync(queue, logger, server)

        logger.exception.assert_called_once_with(
            "IMAP login failed due to SSL error. (This is often due to a timeout)"
        )
        server.logout.assert_called_once_with()

    @mock.patch(
        "helpdesk.email.extract_email_metadata", return_value=mock.sentinel.ticket
    )
    @mock.patch("helpdesk.email.os.unlink", side_effect=OSError("Permission denied"))
    @mock.patch("helpdesk.email.isfile", return_value=True)
    @mock.patch("helpdesk.email.os.listdir", return_value=["message.eml"])
    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="Subject: Test")
    def test_local_mailbox_deletion_failure_is_logged(
        self, mocked_open, mocked_listdir, mocked_isfile, mocked_unlink, mocked_extract
    ):
        from helpdesk.email import process_queue

        queue = mock.Mock()
        queue.title = "Test Queue"
        queue.email_box_type = "local"
        queue.email_box_local_dir = "/mail"
        queue.socks_proxy_type = None
        logger = mock.Mock(spec=logging.Logger)

        with mock.patch("helpdesk.email.helpdesk_settings.QUEUE_EMAIL_BOX_TYPE", None):
            process_queue(queue, logger)

        mocked_extract.assert_called_once()
        mocked_unlink.assert_called_once_with(os.path.join("/mail", "message.eml"))
        logger.error.assert_called_once_with(
            "Unable to delete message %d (%s).", 1, "Permission denied"
        )

    @mock.patch("helpdesk.email.extract_email_metadata")
    def test_pop3_ignored_message_is_not_deleted(self, mocked_extract):
        from helpdesk.exceptions import IgnoreTicketException

        queue = mock.Mock()
        queue.email_box_user = "user@example.com"
        queue.email_box_pass = "password"
        logger = mock.Mock(spec=logging.Logger)
        server = mock.Mock()
        server.list.return_value = ("+OK", ["1 100"])
        server.retr.return_value = ("+OK", ["Subject: Ignored", "", "Body"])
        mocked_extract.side_effect = IgnoreTicketException("Ignored sender")

        pop3_sync(queue, logger, server)

        server.dele.assert_not_called()
        logger.warning.assert_any_call(
            "Message 1 was ignored and will be left on POP3 server"
        )
        server.quit.assert_called_once_with()

    @mock.patch("helpdesk.email.extract_email_metadata")
    def test_pop3_delete_ignored_message(self, mocked_extract):
        from helpdesk.exceptions import DeleteIgnoredTicketException

        queue = mock.Mock()
        queue.email_box_user = "user@example.com"
        queue.email_box_pass = "password"
        logger = mock.Mock(spec=logging.Logger)
        server = mock.Mock()
        server.list.return_value = ("+OK", ["1 100"])
        server.retr.return_value = ("+OK", ["Subject: Delete", "", "Body"])
        mocked_extract.side_effect = DeleteIgnoredTicketException("Delete sender")

        pop3_sync(queue, logger, server)

        server.dele.assert_called_once_with("1")
        logger.warning.assert_any_call(
            "Message 1 was ignored and deleted from POP3 server"
        )
        server.quit.assert_called_once_with()

    def test_imap_authentication_failure_logs_out(self):
        import imaplib

        from helpdesk.email import imap_sync

        queue = mock.Mock()
        queue.email_box_user = "user@example.com"
        queue.email_box_pass = "password"
        queue.email_box_imap_folder = "INBOX"
        logger = mock.Mock(spec=logging.Logger)
        server = mock.Mock()
        server.login.side_effect = imaplib.IMAP4.abort("Authentication failed")

        with self.assertRaises(SystemExit):
            imap_sync(queue, logger, server)

        logger.error.assert_called_once_with(
            "IMAP login failed. Check that the server is accessible and that "
            "the username and password are correct."
        )
        server.logout.assert_called_once_with()
        server.search.assert_not_called()

    def test_imap_ssl_failure_logs_out(self):
        import ssl

        from helpdesk.email import imap_sync

        queue = mock.Mock()
        queue.email_box_user = "user@example.com"
        queue.email_box_pass = "password"
        queue.email_box_imap_folder = "INBOX"
        logger = mock.Mock(spec=logging.Logger)
        server = mock.Mock()
        server.login.side_effect = ssl.SSLError("SSL connection failed")

        with self.assertRaises(SystemExit):
            imap_sync(queue, logger, server)

        logger.error.assert_called_once_with(
            "IMAP login failed due to SSL error. This is often due to a timeout. "
            "Please check your connection and try again."
        )
        server.logout.assert_called_once_with()
        server.search.assert_not_called()

    @mock.patch("helpdesk.email.extract_email_metadata")
    def test_imap_message_processing_outcomes(self, mocked_extract):
        from helpdesk.email import imap_sync
        from helpdesk.exceptions import (
            DeleteIgnoredTicketException,
            IgnoreTicketException,
        )

        cases = [
            (
                "ignored",
                IgnoreTicketException("Ignored sender"),
                False,
                "warning",
                "Message b'1' was ignored and will be left on IMAP server",
            ),
            (
                "delete_ignored",
                DeleteIgnoredTicketException("Delete sender"),
                True,
                "warning",
                "Message b'1' was ignored and deleted from IMAP server",
            ),
            (
                "processing_error",
                TypeError("Invalid message"),
                False,
                "exception",
                "Unexpected error processing message b'1'",
            ),
            (
                "no_ticket",
                None,
                False,
                "warning",
                "Message b'1' was not successfully processed, and will be left on IMAP server",
            ),
        ]

        for name, result, should_delete, log_method, message in cases:
            with self.subTest(name=name):
                queue = mock.Mock()
                queue.email_box_user = "user@example.com"
                queue.email_box_pass = "password"
                queue.email_box_imap_folder = "INBOX"
                logger = mock.Mock(spec=logging.Logger)
                server = mock.Mock()
                server.search.return_value = ("OK", [b"1"])
                server.fetch.return_value = (
                    "OK",
                    [(b"1 (RFC822)", b"Subject: Test\r\n\r\nBody")],
                )

                mocked_extract.reset_mock()
                if isinstance(result, Exception):
                    mocked_extract.side_effect = result
                    mocked_extract.return_value = None
                else:
                    mocked_extract.side_effect = None
                    mocked_extract.return_value = result

                imap_sync(queue, logger, server)

                mocked_extract.assert_called_with(
                    message="Subject: Test\r\n\r\nBody",
                    queue=queue,
                    logger=logger,
                )
                if should_delete:
                    server.store.assert_called_once_with(b"1", "+FLAGS", "\\Deleted")
                else:
                    server.store.assert_not_called()

                getattr(logger, log_method).assert_any_call(message)
                server.expunge.assert_called_once_with()
                server.close.assert_called_once_with()
                server.logout.assert_called_once_with()

    @mock.patch("helpdesk.email.extract_email_metadata")
    @mock.patch("helpdesk.email.oauth2lib.BackendApplicationClient")
    @mock.patch("helpdesk.email.requests_oauthlib.OAuth2Session")
    def test_oauth_message_processing_outcomes(
        self, mocked_session, mocked_client, mocked_extract
    ):
        from helpdesk.email import imap_oauth_sync
        from helpdesk.exceptions import (
            DeleteIgnoredTicketException,
            IgnoreTicketException,
        )

        mocked_session.return_value.fetch_token.return_value = {
            "access_token": "test-token"
        }

        cases = [
            ("ignored", IgnoreTicketException("Ignored sender"), False, "warning"),
            ("delete_ignored", DeleteIgnoredTicketException("Delete"), True, "warning"),
            ("processing_error", TypeError("Invalid message"), False, "exception"),
            ("no_ticket", None, False, "warning"),
        ]

        for name, result, should_delete, log_method in cases:
            with self.subTest(name=name):
                queue = mock.Mock()
                queue.email_box_user = "user@example.com"
                queue.email_box_imap_folder = "INBOX"
                logger = mock.Mock(spec=logging.Logger)
                server = mock.Mock()
                server.search.return_value = ("OK", [b"1"])
                server.fetch.return_value = (
                    "OK",
                    [(b"1 (RFC822)", b"Subject: Test\r\n\r\nBody")],
                )

                mocked_extract.reset_mock()
                mocked_extract.side_effect = (
                    result if isinstance(result, Exception) else None
                )
                mocked_extract.return_value = result

                imap_oauth_sync(queue, logger, server)

                mocked_extract.assert_called_once_with(
                    message="Subject: Test\r\n\r\nBody",
                    queue=queue,
                    logger=logger,
                )
                server.authenticate.assert_called_once()
                server.select.assert_called_once_with("INBOX")

                if should_delete:
                    server.store.assert_called_once_with(b"1", "+FLAGS", "\\Deleted")
                    self.assertEqual(server.expunge.call_count, 2)
                else:
                    server.store.assert_not_called()
                    server.expunge.assert_called_once_with()

                self.assertTrue(getattr(logger, log_method).called)
                server.close.assert_called_once_with()
                server.logout.assert_called_once_with()

    def test_missing_pysocks_raises_helpful_error(self):
        import builtins

        from helpdesk.email import process_queue

        queue = mock.Mock()
        queue.title = "Proxy Queue"
        queue.socks_proxy_type = "socks5"
        queue.socks_proxy_host = "127.0.0.1"
        queue.socks_proxy_port = 1080
        logger = mock.Mock(spec=logging.Logger)

        original_import = builtins.__import__

        def import_without_socks(name, *args, **kwargs):
            if name == "socks":
                raise ImportError("No module named socks")
            return original_import(name, *args, **kwargs)

        with (
            mock.patch("builtins.__import__", side_effect=import_without_socks),
            self.assertRaisesRegex(ImportError, "no socks library was installed"),
        ):
            process_queue(queue, logger)

        logger.error.assert_called_once_with(
            "Queue has been configured with proxy settings, "
            "but no socks library was installed. Try to "
            "install PySocks via PyPI."
        )

    def test_socks_proxy_configuration(self):
        import socket
        import sys
        import types

        from helpdesk.email import process_queue

        fake_socks = types.ModuleType("socks")
        fake_socks.SOCKS4 = 1
        fake_socks.SOCKS5 = 2
        fake_socks.socksocket = mock.Mock()
        fake_socks.set_default_proxy = mock.Mock()

        for proxy_name, proxy_constant in (
            ("socks4", fake_socks.SOCKS4),
            ("socks5", fake_socks.SOCKS5),
        ):
            with self.subTest(proxy=proxy_name):
                queue = mock.Mock()
                queue.title = "Proxy Queue"
                queue.socks_proxy_type = proxy_name
                queue.socks_proxy_host = "127.0.0.1"
                queue.socks_proxy_port = 1080
                queue.email_box_type = "local"
                queue.email_box_local_dir = "/empty-mail"
                logger = mock.Mock(spec=logging.Logger)

                fake_socks.set_default_proxy.reset_mock()

                with (
                    mock.patch.dict(sys.modules, {"socks": fake_socks}),
                    mock.patch.object(socket, "socket"),
                    mock.patch("helpdesk.email.os.listdir", return_value=[]),
                    mock.patch(
                        "helpdesk.email.helpdesk_settings.QUEUE_EMAIL_BOX_TYPE",
                        None,
                    ),
                ):
                    process_queue(queue, logger)

                    self.assertIs(socket.socket, fake_socks.socksocket)

                fake_socks.set_default_proxy.assert_called_once_with(
                    proxy_type=proxy_constant,
                    addr="127.0.0.1",
                    port=1080,
                )

    @mock.patch("helpdesk.email.extract_email_metadata")
    def test_pop3_byte_messages_are_processed(self, mocked_extract):
        queue = mock.Mock()
        queue.email_box_user = "user@example.com"
        queue.email_box_pass = "password"
        logger = mock.Mock(spec=logging.Logger)
        server = mock.Mock()
        server.list.return_value = ("+OK", [b"1 42"])
        server.retr.return_value = (
            "+OK",
            [b"Subject: Test", b"", b"Message body"],
        )
        mocked_extract.return_value = mock.sentinel.ticket

        pop3_sync(queue, logger, server)

        mocked_extract.assert_called_once_with(
            message="Subject: Test\n\nMessage body",
            queue=queue,
            logger=logger,
        )
        server.dele.assert_called_once_with("1")
        server.quit.assert_called_once()

    def test_imap_starttls_failure_continues_processing(self):
        from helpdesk.email import imap_sync

        queue = mock.Mock()
        queue.email_box_user = "user@example.com"
        queue.email_box_pass = "password"
        queue.email_box_imap_folder = "INBOX"
        logger = mock.Mock(spec=logging.Logger)
        server = mock.Mock()
        server.starttls.side_effect = RuntimeError("TLS unavailable")
        server.search.return_value = ("OK", [])

        imap_sync(queue, logger, server)

        logger.warning.assert_called_once_with(
            "IMAP4 StartTLS unsupported or failed. Connection will be unencrypted."
        )
        server.login.assert_called_once_with("user@example.com", "password")
        server.select.assert_called_once_with("INBOX")
        server.expunge.assert_called_once()
        server.close.assert_called_once()
        server.logout.assert_called_once()

    def test_imap_retrieval_failure_logs_error_and_closes_connection(self):
        import imaplib

        from helpdesk.email import imap_sync

        queue = mock.Mock()
        queue.email_box_user = "user@example.com"
        queue.email_box_pass = "password"
        queue.email_box_imap_folder = "INBOX"
        logger = mock.Mock(spec=logging.Logger)
        server = mock.Mock()
        server.search.side_effect = imaplib.IMAP4.error("Search failed")

        imap_sync(queue, logger, server)

        logger.error.assert_called_once_with(
            "IMAP retrieve failed. Is the folder '%s' spelled correctly, and does it exist on the server?",
            "INBOX",
        )
        server.expunge.assert_called_once()
        server.close.assert_called_once()
        server.logout.assert_called_once()

    @mock.patch("helpdesk.email.oauth2lib.BackendApplicationClient")
    @mock.patch("helpdesk.email.requests_oauthlib.OAuth2Session")
    def test_oauth_retrieval_failure_logs_error_and_closes_connection(
        self, mocked_session, mocked_client
    ):
        import imaplib

        from helpdesk.email import imap_oauth_sync

        mocked_session.return_value.fetch_token.return_value = {
            "access_token": "test-token"
        }

        queue = mock.Mock()
        queue.email_box_user = "user@example.com"
        queue.email_box_imap_folder = "INBOX"
        logger = mock.Mock(spec=logging.Logger)
        server = mock.Mock()
        server.search.side_effect = imaplib.IMAP4.error("Search failed")

        imap_oauth_sync(queue, logger, server)

        server.authenticate.assert_called_once()
        server.select.assert_called_once_with("INBOX")
        logger.error.assert_called_once_with(
            "IMAP retrieve failed. Is the folder '%s' spelled correctly, and does it exist on the server?",
            "INBOX",
        )
        server.store.assert_not_called()
        server.expunge.assert_called_once()
        server.close.assert_called_once()
        server.logout.assert_called_once()

    @mock.patch("helpdesk.email.extract_email_metadata")
    @mock.patch("helpdesk.email.os.unlink")
    @mock.patch("helpdesk.email.isfile", return_value=True)
    @mock.patch("helpdesk.email.os.listdir", return_value=["message.eml"])
    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="Subject: Test")
    def test_local_mailbox_ignored_message_is_preserved(
        self, mocked_open, mocked_listdir, mocked_isfile, mocked_unlink, mocked_extract
    ):
        from helpdesk.email import process_queue
        from helpdesk.exceptions import IgnoreTicketException

        queue = mock.Mock()
        queue.title = "Test Queue"
        queue.email_box_type = "local"
        queue.email_box_local_dir = "/mail"
        queue.socks_proxy_type = None
        logger = mock.Mock(spec=logging.Logger)
        mocked_extract.side_effect = IgnoreTicketException("Ignored sender")

        with mock.patch("helpdesk.email.helpdesk_settings.QUEUE_EMAIL_BOX_TYPE", None):
            process_queue(queue, logger)

        mocked_extract.assert_called_once_with(
            message="Subject: Test", queue=queue, logger=logger
        )
        mocked_unlink.assert_not_called()
        logger.warning.assert_called_once_with(
            "Message %d was ignored and will be left in local directory", 1
        )

    @mock.patch("helpdesk.email.extract_email_metadata")
    @mock.patch("helpdesk.email.os.unlink")
    @mock.patch("helpdesk.email.isfile", return_value=True)
    @mock.patch("helpdesk.email.os.listdir", return_value=["message.eml"])
    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="Subject: Test")
    def test_local_mailbox_delete_ignored_message(
        self, mocked_open, mocked_listdir, mocked_isfile, mocked_unlink, mocked_extract
    ):
        from helpdesk.email import process_queue
        from helpdesk.exceptions import DeleteIgnoredTicketException

        queue = mock.Mock()
        queue.title = "Test Queue"
        queue.email_box_type = "local"
        queue.email_box_local_dir = "/mail"
        queue.socks_proxy_type = None
        logger = mock.Mock(spec=logging.Logger)
        mocked_extract.side_effect = DeleteIgnoredTicketException("Delete sender")

        with mock.patch("helpdesk.email.helpdesk_settings.QUEUE_EMAIL_BOX_TYPE", None):
            process_queue(queue, logger)

        mocked_unlink.assert_called_once()
        logger.warning.assert_called_once_with(
            "Message %d was ignored and deleted local directory", 1
        )

    @mock.patch("helpdesk.email.extract_email_metadata", return_value=None)
    @mock.patch("helpdesk.email.os.unlink")
    @mock.patch("helpdesk.email.isfile", return_value=True)
    @mock.patch("helpdesk.email.os.listdir", return_value=["message.eml"])
    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="Subject: Test")
    def test_local_mailbox_unsuccessful_message_is_preserved(
        self, mocked_open, mocked_listdir, mocked_isfile, mocked_unlink, mocked_extract
    ):
        from helpdesk.email import process_queue

        queue = mock.Mock()
        queue.title = "Test Queue"
        queue.email_box_type = "local"
        queue.email_box_local_dir = "/mail"
        queue.socks_proxy_type = None
        logger = mock.Mock(spec=logging.Logger)

        with mock.patch("helpdesk.email.helpdesk_settings.QUEUE_EMAIL_BOX_TYPE", None):
            process_queue(queue, logger)

        mocked_extract.assert_called_once()
        mocked_unlink.assert_not_called()
        logger.warning.assert_called_once_with(
            "Message %d was not successfully processed, and will be left in local directory",
            1,
        )


class ProcessEmailLoggingTests(SimpleTestCase):
    @mock.patch("helpdesk.email.process_queue")
    @mock.patch("helpdesk.email.logging.FileHandler")
    @mock.patch("helpdesk.email.Queue.objects.filter")
    def test_file_handler_is_created_and_cleaned_up(
        self, mocked_filter, mocked_file_handler, mocked_process_queue
    ):
        from helpdesk.email import process_email

        queue = mock.Mock()
        queue.slug = "test"
        queue.email_address = "test@example.com"
        queue.logging_type = "info"
        queue.logging_dir = "logs"
        queue.email_box_last_check = timezone.now() - timedelta(minutes=30)
        queue.email_box_interval = 0
        mocked_filter.return_value = [queue]

        handler = mock.Mock()
        handler.level = logging.NOTSET
        mocked_file_handler.return_value = handler
        self.addCleanup(
            logging.getLogger("django.helpdesk.queue.test").removeHandler,
            handler,
        )

        with (
            mock.patch("helpdesk.email.timezone.now") as mocked_now,
            mock.patch("helpdesk.email.timedelta") as mocked_timedelta,
        ):
            mocked_now.return_value = queue.email_box_last_check + timedelta(minutes=1)
            mocked_timedelta.side_effect = timedelta
            process_email()

        mocked_file_handler.assert_called_once()
        handler.close.assert_called_once()

    @mock.patch("helpdesk.email.process_queue")
    @mock.patch("helpdesk.email.Queue.objects.filter")
    def test_logging_disabled_does_not_create_file_handler(
        self, mocked_filter, mocked_process_queue
    ):
        from helpdesk.email import process_email

        queue = mock.Mock()
        queue.slug = "test"
        queue.email_address = None
        queue.logging_type = "none"
        queue.logging_dir = "logs"
        queue.email_box_last_check = timezone.now() - timedelta(minutes=30)
        queue.email_box_interval = 0
        mocked_filter.return_value = [queue]

        with (
            mock.patch("helpdesk.email.logging.FileHandler") as mocked_handler,
            mock.patch("helpdesk.email.timezone.now") as mocked_now,
            mock.patch("helpdesk.email.timedelta") as mocked_timedelta,
        ):
            mocked_now.return_value = queue.email_box_last_check + timedelta(minutes=1)
            mocked_timedelta.side_effect = timedelta
            process_email()

        mocked_handler.assert_not_called()
        mocked_process_queue.assert_called_once()

    @mock.patch("helpdesk.email.process_queue", side_effect=RuntimeError("Queue error"))
    @mock.patch("helpdesk.email.logging.FileHandler")
    @mock.patch("helpdesk.email.Queue.objects.filter")
    def test_file_handler_is_cleaned_up_after_queue_failure(
        self, mocked_filter, mocked_file_handler, mocked_process_queue
    ):
        from helpdesk.email import process_email

        queue = mock.Mock()
        queue.slug = "test"
        queue.email_address = None
        queue.logging_type = "info"
        queue.logging_dir = "logs"
        queue.email_box_last_check = timezone.now() - timedelta(minutes=30)
        queue.email_box_interval = 0
        mocked_filter.return_value = [queue]

        handler = mock.Mock()
        handler.level = logging.NOTSET
        mocked_file_handler.return_value = handler
        self.addCleanup(
            logging.getLogger("django.helpdesk.queue.test").removeHandler,
            handler,
        )

        with mock.patch("helpdesk.email.timezone.now") as mocked_now:
            mocked_now.return_value = queue.email_box_last_check + timedelta(minutes=1)
            process_email()

        handler.close.assert_called_once()
