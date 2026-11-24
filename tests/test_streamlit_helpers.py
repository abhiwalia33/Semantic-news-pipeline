import unittest

from streamlit_helpers import esc, safe_url, snippet


class EscTests(unittest.TestCase):
    def test_escapes_markup_and_quotes(self):
        self.assertEqual(
            esc('<script>alert("x")</script> & \'y\''),
            "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &#x27;y&#x27;",
        )

    def test_none_and_non_strings(self):
        self.assertEqual(esc(None), "")
        self.assertEqual(esc(42), "42")

    def test_plain_text_unchanged(self):
        self.assertEqual(esc("AI safety news"), "AI safety news")


class SnippetTests(unittest.TestCase):
    def test_truncates_before_escaping(self):
        # Escaping first would turn "&" into "&amp;" and could cut it mid-entity
        self.assertEqual(snippet("ab&cd", max_chars=3), "ab&amp;")

    def test_strips_and_escapes(self):
        self.assertEqual(snippet("  <b>hi</b>  "), "&lt;b&gt;hi&lt;/b&gt;")

    def test_none(self):
        self.assertEqual(snippet(None), "")


class SafeUrlTests(unittest.TestCase):
    def test_http_urls_are_escaped(self):
        self.assertEqual(
            safe_url('https://example.com/a?x=1&y="2"'),
            "https://example.com/a?x=1&amp;y=&quot;2&quot;",
        )

    def test_non_http_schemes_rejected(self):
        for url in ("javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,x", "", None):
            with self.subTest(url=url):
                self.assertEqual(safe_url(url), "#")


if __name__ == "__main__":
    unittest.main()
