import os
import unittest
from datetime import datetime, timezone
from unittest import mock

# connection.py calls create_engine() at import time; give it a dummy URL so
# importing ingestion never needs a real database (create_engine doesn't connect).
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:1/test")

from app.schemas.news import NewsItem  # noqa: E402
from app.services import ingestion  # noqa: E402


def make_item(source: str, source_id: str) -> NewsItem:
    return NewsItem(
        source=source,
        source_id=source_id,
        title=f"Title {source_id}",
        url=f"https://example.com/{source_id}",
        scraped_at=datetime.now(timezone.utc),
    )


class FailingScraper:
    source = "broken"

    def scrape(self, limit: int):
        raise TimeoutError("feed timed out")


class FakeScraper:
    def __init__(self, source: str, items: list[NewsItem]):
        self.source = source
        self.items = items
        self.limits: list[int] = []

    def scrape(self, limit: int):
        self.limits.append(limit)
        return self.items[:limit]


class FakeSession:
    def __init__(self):
        self.closed = False
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class FakeRepository:
    """Stands in for insert_news_item: returns a row once per (source, source_id)."""

    def __init__(self, fail_ids: set[str] = frozenset()):
        self.seen: set[tuple[str, str]] = set()
        self.fail_ids = fail_ids

    def __call__(self, db, item: NewsItem):
        if item.source_id in self.fail_ids:
            raise RuntimeError("db error")
        key = (item.source, item.source_id)
        if key in self.seen:
            return None  # mimics ON CONFLICT DO NOTHING
        self.seen.add(key)
        return mock.Mock(title=item.title)


class RunIngestionTests(unittest.TestCase):
    def run_with(self, scrapers, repo=None, **kwargs):
        repo = repo or FakeRepository()
        session = FakeSession()
        with mock.patch.object(ingestion, "insert_news_item", repo), \
                mock.patch("builtins.print"), \
                self.assertLogs("app.services.ingestion", level="INFO") as logs:
            results = ingestion.run_ingestion(
                scrapers=scrapers, session_factory=lambda: session, **kwargs
            )
        return results, repo, session, logs

    def test_failing_source_does_not_stop_others(self):
        good = FakeScraper("good", [make_item("good", "1"), make_item("good", "2")])
        results, repo, session, logs = self.run_with([(FailingScraper(), 5), (good, 5)])

        broken_stats, good_stats = results
        self.assertEqual(broken_stats.source, "broken")
        self.assertEqual(broken_stats.failures, 1)
        self.assertIn("TimeoutError", broken_stats.error)
        self.assertEqual(broken_stats.fetched, 0)

        self.assertEqual(good_stats.fetched, 2)
        self.assertEqual(good_stats.inserted, 2)
        self.assertEqual(good_stats.failures, 0)
        self.assertIsNone(good_stats.error)
        self.assertEqual(repo.seen, {("good", "1"), ("good", "2")})

        self.assertTrue(session.closed)
        self.assertTrue(any("Source broken failed" in line for line in logs.output))

    def test_counts_duplicates_and_insert_failures(self):
        items = [make_item("src", "1"), make_item("src", "1"), make_item("src", "bad")]
        repo = FakeRepository(fail_ids={"bad"})
        results, _, session, _ = self.run_with([(FakeScraper("src", items), 10)], repo=repo)

        stats = results[0]
        self.assertEqual(
            (stats.fetched, stats.inserted, stats.duplicates, stats.failures), (3, 1, 1, 1)
        )
        self.assertEqual(session.rollbacks, 1)
        self.assertIn("fetched=3 inserted=1 duplicates=1 failures=1", stats.summary())

    def test_uses_default_limit_per_source(self):
        a, b = FakeScraper("a", []), FakeScraper("b", [])
        self.run_with([(a, 30), (b, 20)])
        self.assertEqual((a.limits, b.limits), ([30], [20]))

    def test_limit_argument_overrides_all_sources(self):
        a, b = FakeScraper("a", []), FakeScraper("b", [])
        self.run_with([(a, 30), (b, 20)], limit=3)
        self.assertEqual((a.limits, b.limits), ([3], [3]))

    def test_env_var_overrides_all_sources(self):
        a = FakeScraper("a", [])
        with mock.patch.dict(os.environ, {ingestion.LIMIT_ENV_VAR: "3"}):
            self.run_with([(a, 30)])
        self.assertEqual(a.limits, [3])

    def test_invalid_env_var_falls_back_to_defaults(self):
        a = FakeScraper("a", [])
        with mock.patch.dict(os.environ, {ingestion.LIMIT_ENV_VAR: "abc"}):
            self.run_with([(a, 30)])
        self.assertEqual(a.limits, [30])


class DefaultScrapersTests(unittest.TestCase):
    def test_all_sources_with_expected_limits(self):
        configured = {s.source: limit for s, limit in ingestion.default_scrapers()}
        expected = {"hackernews": 30, "arxiv": 20}
        expected.update({name: 20 for name in ingestion.DEFAULT_FEEDS})
        self.assertEqual(configured, expected)


if __name__ == "__main__":
    unittest.main()
