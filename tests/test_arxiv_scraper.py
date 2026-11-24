import unittest
from pathlib import Path
from unittest import mock

import requests

from app.scrapers import arxiv
from app.scrapers.arxiv import ArxivScraper, arxiv_id, parse_feed

FIXTURES = Path(__file__).parent / "fixtures" / "arxiv"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def no_network(*args, **kwargs):
    raise AssertionError("tests must not touch the network")


class ArxivIdTests(unittest.TestCase):
    def test_strips_version_suffix(self):
        self.assertEqual(arxiv_id("http://arxiv.org/abs/2611.31240v1"), "2611.31240")
        self.assertEqual(arxiv_id("http://arxiv.org/abs/2611.31240v12"), "2611.31240")

    def test_handles_old_style_ids(self):
        self.assertEqual(arxiv_id("http://arxiv.org/abs/cs/0112017v2"), "cs/0112017")

    def test_unversioned_and_invalid(self):
        self.assertEqual(arxiv_id("http://arxiv.org/abs/2611.31240"), "2611.31240")
        self.assertIsNone(arxiv_id("http://example.com/nothing"))


@mock.patch("app.scrapers.arxiv.requests.get", no_network)
class ParseFeedTests(unittest.TestCase):
    def test_maps_entry_to_news_item(self):
        items = parse_feed(load("recent.xml"), limit=20)

        self.assertEqual(len(items), 3)
        first = items[0]
        self.assertEqual(first.source, "arxiv")
        self.assertEqual(first.source_id, "2611.31240")
        self.assertEqual(
            first.title,
            "Pruning Autonomous Driving VLAs: What to Preserve for Reasoning and Action",
        )
        self.assertEqual(str(first.url), "https://arxiv.org/abs/2611.31240")
        self.assertEqual(first.author, "Seongchan Kim, Soowon Son, Seungryong Kim")
        self.assertTrue(first.content.startswith("Reasoning vision-language-action"))
        self.assertNotIn("\n", first.content)
        self.assertIsNotNone(first.scraped_at.tzinfo)

    def test_new_version_has_same_source_id(self):
        items = parse_feed(load("recent.xml"), limit=20)
        revised = items[1]
        self.assertEqual(revised.source_id, "2611.30001")
        self.assertEqual(str(revised.url), "https://arxiv.org/abs/2611.30001")
        self.assertEqual(revised.title, "A Revised Paper With a Wrapped Title")
        self.assertEqual(revised.author, "Single Author")

    def test_old_style_id_and_missing_authors(self):
        legacy = parse_feed(load("recent.xml"), limit=20)[2]
        self.assertEqual(legacy.source_id, "cs/0112017")
        self.assertIsNone(legacy.author)

    def test_respects_limit(self):
        self.assertEqual(len(parse_feed(load("recent.xml"), limit=2)), 2)

    def test_api_error_entry_logs_and_returns_empty(self):
        with self.assertLogs("app.scrapers.arxiv", level="WARNING") as logs:
            self.assertEqual(parse_feed(load("error.xml"), limit=20), [])
        self.assertIn("incorrect id format", logs.output[0])

    def test_empty_or_garbage_response_logs_and_returns_empty(self):
        for raw in (b"", b"<html>Service Unavailable</html>"):
            with self.subTest(raw=raw), self.assertLogs("app.scrapers.arxiv", level="WARNING"):
                self.assertEqual(parse_feed(raw, limit=20), [])


class ArxivScraperTests(unittest.TestCase):
    def test_single_request_with_expected_params(self):
        response = mock.Mock(content=load("recent.xml"))
        with mock.patch("app.scrapers.arxiv.requests.get", return_value=response) as get:
            items = ArxivScraper().scrape()

        get.assert_called_once()
        url = get.call_args.args[0]
        kwargs = get.call_args.kwargs
        self.assertTrue(url.startswith("https://"))
        self.assertEqual(kwargs["timeout"], arxiv.REQUEST_TIMEOUT)
        self.assertEqual(
            kwargs["params"],
            {
                "search_query": "cat:cs.AI OR cat:cs.CL OR cat:cs.LG",
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "start": 0,
                "max_results": 20,
            },
        )
        self.assertEqual(len(items), 3)
        self.assertEqual(ArxivScraper.source, "arxiv")

    def test_limit_passed_as_max_results(self):
        response = mock.Mock(content=load("recent.xml"))
        with mock.patch("app.scrapers.arxiv.requests.get", return_value=response) as get:
            items = ArxivScraper().scrape(limit=1)
        self.assertEqual(get.call_args.kwargs["params"]["max_results"], 1)
        self.assertEqual(len(items), 1)

    def test_request_failure_logs_and_returns_empty(self):
        for error in (requests.Timeout("timed out"), requests.HTTPError("503")):
            with self.subTest(error=error), mock.patch(
                "app.scrapers.arxiv.requests.get", side_effect=error
            ), self.assertLogs("app.scrapers.arxiv", level="WARNING"):
                self.assertEqual(ArxivScraper().scrape(), [])

    def test_http_error_status_logs_and_returns_empty(self):
        response = mock.Mock()
        response.raise_for_status.side_effect = requests.HTTPError("503 Server Error")
        with mock.patch("app.scrapers.arxiv.requests.get", return_value=response), \
                self.assertLogs("app.scrapers.arxiv", level="WARNING"):
            self.assertEqual(ArxivScraper().scrape(), [])


if __name__ == "__main__":
    unittest.main()
