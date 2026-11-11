from django.test import SimpleTestCase

from helpdesk.templatetags.helpdesk_util import datetime_string_format


class DateTimeStringFormatTests(SimpleTestCase):
    def test_datetime_format(self):
        self.assertEqual(
            datetime_string_format("2026-11-11T14:30"),
            "Nov. 11, 2026, 2:30 p.m.",
        )

    def test_date_format(self):
        self.assertEqual(
            datetime_string_format("2026-11-11"),
            "Nov. 11, 2026",
        )

    def test_time_format(self):
        self.assertEqual(
            datetime_string_format("14:30:00"),
            "2:30 p.m.",
        )

    def test_invalid_value_returns_original(self):
        self.assertEqual(datetime_string_format("invalid"), "invalid")

    def test_none_returns_empty_string(self):
        self.assertEqual(datetime_string_format(None), "")
