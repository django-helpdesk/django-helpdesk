"""Every URL rendered from markdown must use a scheme from ALLOWED_URL_SCHEMES,
whatever markdown syntax produced it.
"""

from html.parser import HTMLParser

from django.test import TestCase

from helpdesk.models import get_markdown

# Any scheme absent from ALLOWED_URL_SCHEMES; no working payload needed.
FORBIDDEN = "notallowed:"


class UrlCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.urls += [value for name, value in attrs if name in ("href", "src")]


def rendered_urls(text):
    collector = UrlCollector()
    collector.feed(get_markdown(text))
    return collector.urls


class MarkdownUrlSchemeTestCase(TestCase):
    def assertNoForbiddenScheme(self, text):
        for url in rendered_urls(text):
            as_read = "".join(c for c in url if c not in "\t\n\r").strip().lower()
            self.assertFalse(
                as_read.startswith(FORBIDDEN),
                f"{url!r} kept a scheme outside ALLOWED_URL_SCHEMES",
            )

    def test_inline_link(self):
        self.assertNoForbiddenScheme("[t](notallowed:x)")

    def test_reference_link(self):
        self.assertNoForbiddenScheme("[t][a]\n\n[a]: notallowed:x")

    def test_reference_image(self):
        self.assertNoForbiddenScheme("![t][a]\n\n[a]: notallowed:x")

    def test_entity_encoded_scheme_in_an_inline_link(self):
        self.assertNoForbiddenScheme("[t](&#110;otallowed:x)")
        self.assertNoForbiddenScheme("[t](not&#9;allowed:x)")

    def test_entity_encoded_scheme_in_a_reference(self):
        self.assertNoForbiddenScheme("[t][a]\n\n[a]: &#110;otallowed:x")
        self.assertNoForbiddenScheme("[t][a]\n\n[a]: not&#10;allowed:x")

    def test_allowed_schemes_and_relative_urls_survive(self):
        urls = rendered_urls(
            "[a](https://example.com/a) [b][ref] ![c](/static/c.png)\n\n"
            "[ref]: mailto:someone@example.com"
        )
        self.assertEqual(
            urls,
            ["https://example.com/a", "mailto:someone@example.com", "/static/c.png"],
        )

    def test_code_block_language_class_is_kept(self):
        self.assertIn('class="language-python"', get_markdown("```python\nx = 1\n```"))
