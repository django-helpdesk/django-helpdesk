from django.test import SimpleTestCase

from helpdesk.email import attempt_body_extract_from_html, get_encoded_body


class EmailBodyHelperTests(SimpleTestCase):
    def test_decodes_escaped_ascii_body(self):
        self.assertEqual(
            get_encoded_body(r"Hello\nWorld"),
            "Hello\nWorld",
        )

    def test_extracts_html_body(self):
        body, full_body = attempt_body_extract_from_html(
            "<html><body><p>Hello world</p></body></html>"
        )
        self.assertEqual(body, "Hello world")
        self.assertEqual(full_body, "Hello world")

    def test_html_without_body_returns_empty_result(self):
        body, full_body = attempt_body_extract_from_html(
            "<html><head><title>Test</title></head></html>"
        )
        self.assertEqual(body, "")
        self.assertIsNone(full_body)

    def test_original_email_is_saved_when_enabled(self):
        from unittest import mock

        from django.conf import settings

        from helpdesk.email import add_file_if_always_save_incoming_email_message

        message = "Subject: Test\\n\\nOriginal message body"
        files = []

        with mock.patch.object(
            settings,
            "HELPDESK_ALWAYS_SAVE_INCOMING_EMAIL_MESSAGE",
            True,
            create=True,
        ):
            add_file_if_always_save_incoming_email_message(files, message)

        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].name.endswith(".eml"))
        self.assertEqual(files[0].read(), message.encode("utf-8"))

    def test_html_only_email_extracts_readable_body(self):
        from email.message import EmailMessage

        from helpdesk.email import extract_email_message_content

        message = EmailMessage()
        message.set_content(
            "<html><body><p>HTML-only support request</p></body></html>",
            subtype="html",
        )

        files = []
        body, full_body = extract_email_message_content(
            message,
            files,
            include_chained_msgs=True,
        )

        self.assertIn("HTML-only support request", body)
        self.assertIn("HTML-only support request", full_body)
        self.assertEqual(len(files), 1)

    def test_unnamed_attachment_generates_filename_and_debug_log(self):
        import logging
        from email.message import EmailMessage
        from unittest import mock

        from helpdesk.email import process_as_attachment

        part = EmailMessage()
        part.set_content("Attachment contents")

        files = []
        logger = mock.Mock(spec=logging.Logger)
        logger.isEnabledFor.return_value = True

        process_as_attachment(part, 3, files, logger)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "part-3.txt")
        self.assertEqual(files[0].read(), b"Attachment contents\n")
        logger.debug.assert_called_once_with(
            "Processed MIME as attachment: %s", "part-3.txt"
        )

    def test_unicode_body_is_preserved(self):
        from helpdesk.email import get_encoded_body

        body = "Caf\u00e9 \u2014 r\u00e9sum\u00e9"
        self.assertEqual(get_encoded_body(body), body)

    def test_email_reply_fragments_are_joined(self):
        from unittest import mock

        from helpdesk.email import get_body_from_fragments

        fragments = [
            mock.Mock(content="Current reply"),
            mock.Mock(content="Earlier message"),
        ]

        with mock.patch(
            "helpdesk.email.EmailReplyParser.read",
            return_value=mock.Mock(fragments=fragments),
        ):
            result = get_body_from_fragments("Email content")

        self.assertEqual(result, "Current reply\n\nEarlier message")

    def test_payload_decoding_and_unicode_fallback(self):
        from unittest import mock

        from helpdesk.email import get_email_body_from_part_payload

        part = mock.Mock()
        part.get_payload.return_value = b"Normal message"

        self.assertEqual(
            get_email_body_from_part_payload(part),
            "Normal message",
        )
        part.get_payload.assert_called_with(decode=True)

        part.get_payload.reset_mock()
        part.get_payload.side_effect = [
            b"Invalid \\xff byte",
            "Fallback message",
        ]

        with mock.patch(
            "helpdesk.email.encoding.smart_str",
            side_effect=[
                UnicodeDecodeError("utf-8", b"\\xff", 0, 1, "invalid byte"),
                "Fallback message",
            ],
        ):
            result = get_email_body_from_part_payload(part)

        self.assertEqual(result, "Fallback message")
        self.assertEqual(part.get_payload.call_count, 2)
        part.get_payload.assert_any_call(decode=False)
