# Generic RSS/Atom feed scraper
import html
import logging
import re
from datetime import datetime, timezone
from typing import Callable

import feedparser
import requests
import trafilatura

from app.schemas.news import NewsItem

logger = logging.getLogger(__name__)

# One distinct source label per feed (source + source_id is the dedup key).
DEFAULT_FEEDS: dict[str, str] = {
    "openai_news": "https://openai.com/news/rss.xml",
    "deepmind_blog": "https://deepmind.google/blog/rss.xml",
}

# Feed text shorter than this is treated as a teaser and we try the article page.
MIN_FEED_CONTENT_CHARS = 500
REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (compatible; ai-news-api/0.1)"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _html_to_text(value: str) -> str:
    """Strip tags/entities from feed HTML and collapse whitespace."""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value))).strip()


def _feed_text(entry) -> str:
    """Best text the feed itself provides: full content first, then summary."""
    for block in entry.get("content") or []:
        text = _html_to_text(block.get("value", ""))
        if text:
            return text
    return _html_to_text(entry.get("summary", ""))


def fetch_article_text(url: str) -> str | None:
    """Download a page (with timeout) and extract its main text. Never raises."""
    try:
        response = requests.get(
            url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}
        )
        response.raise_for_status()
        return trafilatura.extract(response.text)
    except Exception as exc:
        logger.warning("Article fetch failed for %s: %s", url, exc)
        return None


def parse_feed(
    raw: bytes | str,
    source: str,
    limit: int,
    fetch_article: Callable[[str], str | None] = fetch_article_text,
) -> list[NewsItem]:
    """Parse raw feed XML into NewsItems.

    Uses the feed's own content; only if it is under MIN_FEED_CONTENT_CHARS
    does it call `fetch_article` and keep that text when it is longer.
    """
    feed = feedparser.parse(raw)

    if not feed.entries:
        logger.warning("Feed %s returned zero entries", source)
        return []

    items: list[NewsItem] = []
    for entry in feed.entries:
        if len(items) >= limit:
            break

        title = _html_to_text(entry.get("title", ""))
        url = entry.get("link")
        if not title or not url:
            continue
        if not url.startswith(("http://", "https://")):
            logger.warning("Skipping %s entry with non-http link %r", source, url)
            continue

        content = _feed_text(entry)
        if len(content) < MIN_FEED_CONTENT_CHARS:
            article = fetch_article(url)
            if article and len(article) > len(content):
                content = article

        try:
            items.append(
                NewsItem(
                    source=source,
                    source_id=entry.get("id") or url,
                    title=title,
                    url=url,
                    author=entry.get("author") or None,
                    content=content or None,
                    scraped_at=datetime.now(timezone.utc),
                )
            )
        except Exception as exc:
            # e.g. an invalid URL; skip the entry, keep the rest of the feed
            logger.warning("Skipping %s entry %r: %s", source, url, exc)

    return items


class RSSScraper:
    """Scraper for a single RSS/Atom feed."""

    def __init__(self, source: str, feed_url: str):
        self.source = source
        self.feed_url = feed_url

    def scrape(self, limit: int) -> list[NewsItem]:
        # Feed-level HTTP errors propagate so the caller can tell "down" from "empty".
        response = requests.get(
            self.feed_url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}
        )
        response.raise_for_status()
        return parse_feed(response.content, self.source, limit)
