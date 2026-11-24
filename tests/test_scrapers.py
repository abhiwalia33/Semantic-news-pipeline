import unittest
from pathlib import Path
from unittest import mock

import requests

from app.scrapers import hackernews, rss
from app.scrapers.hackernews import HackerNewsScraper
from app.scrapers.rss import RSSScraper, fetch_article_text, parse_feed

FIXTURES = Path(__file__).parent / "fixtures" / "rss"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def no_network(*args, **kwargs):
    raise AssertionError("tests must not touch the network")


@mock.patch("app.scrapers.rss.requests.get", no_network)
class ParseFeedTests(unittest.TestCase):
    def test_maps_entry_to_news_item(self):
        fetch = mock.Mock(return_value=None)
        items = parse_feed(load("openai_news.xml"), "openai_news", limit=10, fetch_article=fetch)

        self.assertEqual(len(items), 3)
        first = items[0]
        self.assertEqual(first.source, "openai_news")
        self.assertEqual(
            first.source_id, "https://openai.com/index/searching-for-distant-planets-with-astra"
        )
        self.assertEqual(first.title, "Searching for distant planets with Astra")
        self.assertEqual(
            str(first.url), "https://openai.com/index/searching-for-distant-planets-with-astra"
        )
        self.assertIsNone(first.author)
        self.assertTrue(first.content.startswith("See how two amateur astronomers"))
        self.assertIsNotNone(first.scraped_at.tzinfo)

    def test_source_id_falls_back_to_link_without_guid(self):
        items = parse_feed(load("openai_news.xml"), "openai_news", 10, fetch_article=lambda u: None)
        self.assertEqual(items[1].source_id, "https://openai.com/index/second-story")

    def test_respects_limit(self):
        items = parse_feed(load("openai_news.xml"), "openai_news", 2, fetch_article=lambda u: None)
        self.assertEqual(len(items), 2)

    def test_short_feed_content_uses_longer_article_text(self):
        article = "Full article body. " * 50
        fetch = mock.Mock(return_value=article)
        items = parse_feed(load("openai_news.xml"), "openai_news", 1, fetch_article=fetch)

        fetch.assert_called_once_with(
            "https://openai.com/index/searching-for-distant-planets-with-astra"
        )
        self.assertEqual(items[0].content, article)

    def test_short_feed_content_kept_when_fetch_fails(self):
        items = parse_feed(load("openai_news.xml"), "openai_news", 1, fetch_article=lambda u: None)
        self.assertTrue(items[0].content.startswith("See how two amateur astronomers"))

    def test_long_feed_content_skips_fetch_and_strips_html(self):
        fetch = mock.Mock()
        items = parse_feed(load("long_content.xml"), "example_blog", 10, fetch_article=fetch)

        fetch.assert_not_called()
        # The no-link and bad-URL entries are skipped
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.source_id, "long-1")
        self.assertEqual(item.author, "Jane Researcher")
        self.assertGreaterEqual(len(item.content), rss.MIN_FEED_CONTENT_CHARS)
        self.assertNotIn("<", item.content)
        self.assertIn("markup & entities", item.content)

    def test_empty_feed_logs_warning(self):
        with self.assertLogs("app.scrapers.rss", level="WARNING") as logs:
            items = parse_feed(load("empty.xml"), "empty_feed", 10, fetch_article=no_network)
        self.assertEqual(items, [])
        self.assertIn("zero entries", logs.output[0])


class FetchArticleTextTests(unittest.TestCase):
    def test_returns_none_and_logs_on_error(self):
        with mock.patch(
            "app.scrapers.rss.requests.get", side_effect=requests.Timeout("timed out")
        ) as get, self.assertLogs("app.scrapers.rss", level="WARNING"):
            self.assertIsNone(fetch_article_text("https://example.com/a"))
        self.assertEqual(get.call_args.kwargs["timeout"], rss.REQUEST_TIMEOUT)


class RSSScraperTests(unittest.TestCase):
    def test_scrape_fetches_feed_and_parses(self):
        response = mock.Mock(content=load("long_content.xml"))
        with mock.patch("app.scrapers.rss.requests.get", return_value=response) as get:
            items = RSSScraper("example_blog", "https://example.com/feed.xml").scrape(limit=5)

        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], "https://example.com/feed.xml")
        self.assertEqual(get.call_args.kwargs["timeout"], rss.REQUEST_TIMEOUT)
        self.assertEqual([i.source for i in items], ["example_blog"])

    def test_default_feeds_have_distinct_labels(self):
        self.assertEqual(len(set(rss.DEFAULT_FEEDS)), len(rss.DEFAULT_FEEDS))
        self.assertEqual(len(set(rss.DEFAULT_FEEDS.values())), len(rss.DEFAULT_FEEDS))


class HackerNewsScraperTests(unittest.TestCase):
    def test_adapter_delegates_with_limit(self):
        with mock.patch.object(hackernews, "scrape_top_stories", return_value=[]) as fn:
            scraper = HackerNewsScraper()
            self.assertEqual(scraper.scrape(limit=7), [])
        fn.assert_called_once_with(7)
        self.assertEqual(scraper.source, "hackernews")


if __name__ == "__main__":
    unittest.main()
