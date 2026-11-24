# Ingestion workflow
import argparse
import logging
import os
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.repository import insert_news_item
from app.scrapers.arxiv import ArxivScraper
from app.scrapers.base import Scraper
from app.scrapers.hackernews import HackerNewsScraper
from app.scrapers.rss import DEFAULT_FEEDS, RSSScraper

logger = logging.getLogger(__name__)

# Default number of items to request per source.
HN_LIMIT = 30
RSS_LIMIT = 20  # per feed
ARXIV_LIMIT = 20

# Set to override every source's limit (e.g. INGEST_LIMIT=3 for a quick test run).
LIMIT_ENV_VAR = "INGEST_LIMIT"


@dataclass
class SourceStats:
    source: str
    fetched: int = 0
    inserted: int = 0
    duplicates: int = 0
    failures: int = 0
    error: str | None = None

    def summary(self) -> str:
        status = f"FAILED ({self.error})" if self.error else "ok"
        return (
            f"{self.source}: fetched={self.fetched} inserted={self.inserted} "
            f"duplicates={self.duplicates} failures={self.failures} [{status}]"
        )


def default_scrapers() -> list[tuple[Scraper, int]]:
    """Every configured source paired with its default limit."""
    return [
        (HackerNewsScraper(), HN_LIMIT),
        *((RSSScraper(name, url), RSS_LIMIT) for name, url in DEFAULT_FEEDS.items()),
        (ArxivScraper(), ARXIV_LIMIT),
    ]


def _limit_from_env() -> int | None:
    value = os.getenv(LIMIT_ENV_VAR)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        logger.warning("Ignoring invalid %s=%r", LIMIT_ENV_VAR, value)
        return None


def ingest_source(db: Session, scraper: Scraper, limit: int) -> SourceStats:
    """Scrape one source and insert its items. Never raises."""
    stats = SourceStats(source=scraper.source)

    try:
        items = scraper.scrape(limit)
    except Exception as exc:
        # One failing source (HTTP error, timeout, ...) must not stop the others
        logger.error("Source %s failed: %s", scraper.source, exc)
        stats.failures += 1
        stats.error = f"{type(exc).__name__}: {exc}"
        return stats

    stats.fetched = len(items)
    for item in items:
        try:
            row = insert_news_item(db, item)
        except Exception as exc:
            db.rollback()
            logger.error("Insert failed for %s %s: %s", item.source, item.source_id, exc)
            stats.failures += 1
            continue

        if row:
            stats.inserted += 1
            logger.debug("Inserted: %s", row.title)
        else:
            stats.duplicates += 1
            logger.debug("Skipped (already exists): %s", item.title)

    logger.info(
        "%s: fetched=%d inserted=%d duplicates=%d failures=%d",
        stats.source, stats.fetched, stats.inserted, stats.duplicates, stats.failures,
    )
    return stats


def run_ingestion(
    limit: int | None = None,
    scrapers: list[tuple[Scraper, int]] | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
) -> list[SourceStats]:
    """Scrape every source and save new items.

    `limit` (or the INGEST_LIMIT env var) overrides every source's default limit.
    """
    if limit is None:
        limit = _limit_from_env()
    if scrapers is None:
        scrapers = default_scrapers()

    results: list[SourceStats] = []
    db = session_factory()
    try:
        for scraper, default_limit in scrapers:
            results.append(ingest_source(db, scraper, limit or default_limit))
    finally:
        db.close()

    print("Ingestion summary:")
    for stats in results:
        print(f"  {stats.summary()}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape all sources and save new news items.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=f"Override every source's limit (also settable via {LIMIT_ENV_VAR}).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run_ingestion(limit=args.limit)
