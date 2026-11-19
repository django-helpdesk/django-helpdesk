from contextlib import redirect_stderr
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase

from helpdesk.templatetags.saved_queries import saved_queries


class SavedQueriesTests(SimpleTestCase):
    def test_returns_empty_string_and_reports_database_error(self):
        error_output = StringIO()

        with (
            patch(
                "helpdesk.templatetags.saved_queries.SavedSearch.objects.filter",
                side_effect=RuntimeError("Database unavailable"),
            ),
            redirect_stderr(error_output),
        ):
            result = saved_queries(AnonymousUser())

        self.assertEqual(result, "")
        self.assertIn("Database unavailable", error_output.getvalue())
        self.assertIn("saved_queries", error_output.getvalue())
