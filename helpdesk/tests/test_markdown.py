from django.test import SimpleTestCase
from helpdesk.models import get_markdown


class MarkDown(SimpleTestCase):
    """Test work Markdown functional"""

    def test_markdown_html_tab(self):
        expected_value = "<p>&lt;div&gt;test&lt;div&gt;</p>"
        input_value = "<div>test<div>"
        output_value = get_markdown(input_value)
        self.assertEqual(output_value, expected_value)

    def test_markdown_nl2br(self):
        """warning, after Line 1 - two withespace, esle did't work"""
        expected_value = "<p>Line 1<br />\n                    Line 2</p>"
        input_value = """Line 1  
                    Line 2"""
        output_value = get_markdown(input_value)
        self.assertEqual(output_value, expected_value)

    def test_markdown_fenced_code(self):
        expected_value = '<h1>Title</h1>\n<pre><code class="language-python"># import os\n</code></pre>'
        input_value = """
# Title

```python
# import os
```
        """
        output_value = get_markdown(input_value)
        self.assertEqual(output_value, expected_value)

    def test_markdown_link_correct_protocol(self):
        expected_value = '<p><a href="http://www.yahoo.ru">www.google.com</a></p>'
        input_value = "[www.google.com](http://www.yahoo.ru)"
        output_value = get_markdown(input_value)
        self.assertEqual(output_value, expected_value)

    def test_markdown_link_not_correct_protocol(self):
        expected_value = '<p><a href="//www.yahoo.ru">www.google.com</a></p>'
        input_value = "[www.google.com](aaaa://www.yahoo.ru)"
        output_value = get_markdown(input_value)
        self.assertEqual(output_value, expected_value)

    def test_multiline_markdown_link_with_correct_and_incorrect_protocol(self):
        expected_value = '<p>This<a href="http://alert.javascript.test">XSS</a></p>\n<p>Line 2: <a href="alert(document.domain);">TEST</a></p>'
        input_value = "This[XSS](http://alert.javascript.test)\n\nLine 2: [TEST](javascript:alert(document.domain);)"
        output_value = get_markdown(input_value)
        self.assertEqual(output_value, expected_value)

    def test_multiline_markdown_link_with_correct_and_incorrect_protocol_twice_declared(
        self,
    ):
        expected_value = '<p>This<a href="http://alert.javascript.test">XSS</a></p>\n<p>FAKE IT TILL YOU MAKE IT: <a href="alert(document.domain);">TEST</a></p>'
        input_value = "This[XSS](http://alert.javascript.test)\n\nFAKE IT TILL YOU MAKE IT: [TEST](javascript:javascript:alert(document.domain);)"
        output_value = get_markdown(input_value)
        self.assertEqual(output_value, expected_value)

    def test_markdown_link_with__multiple_incorrect_protocols(self):
        expected_value = '<p>First one:<a href="alert(document.domain);">XSS1</a> ...try again: <a href="alert(document.domain);">XSS2</a></p>'
        input_value = "First one:[XSS1](javascript:alert(document.domain);) ...try again: [XSS2](javascript:javascript:alert(document.domain);)"
        output_value = get_markdown(input_value)
        self.assertEqual(output_value, expected_value)
