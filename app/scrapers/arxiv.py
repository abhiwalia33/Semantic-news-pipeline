# arXiv recent AI papers scraper (arXiv Atom API)
import logging
import re
from datetime import datetime, timezone

import feedparser
import requests

from app.schemas.news import NewsItem

logger = logging.getLogger(__name__)

API_URL = "https://export.arxiv.org/api/query"
SEARCH_QUERY = "cat:cs.AI OR cat:cs.CL OR cat:cs.LG"
REQUEST_TIMEOUT = 30  # the arXiv API can be slow
USER_AGENT = "ai-news-api/0.1"

# Matches new-style (2611.31240v1) and old-style (cs/0112017v2) IDs after /abs/
_ID_RE = re.compile(r"/abs/(?P<id>.+?)(?:v\d+)?$")
_WS_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    """arXiv titles/abstracts contain hard line breaks; collapse whitespace."""
    return _WS_RE.sub(" ", text or "").strip()


def arxiv_id(entry_id: str) -> str | None:
    """'http://arxiv.org/abs/2611.31240v1' -> '2611.31240' (version stripped)."""
    match = _ID_RE.search(entry_id or "")
    return match.group("id") if match else None


def parse_feed(raw: bytes | str, limit: int) -> list[NewsItem]:
    """Parse an arXiv API Atom response into NewsItems."""
    feed = feedparser.parse(raw)

    if not feed.entries:
        logger.warning("arXiv returned zero entries (bozo=%s)", feed.get("bozo"))
        return []

    items: list[NewsItem] = []
    for entry in feed.entries:
        if len(items) >= limit:
            break

        entry_id = entry.get("id", "")
        # The API reports query errors as a single entry under /api/errors
        if "/api/errors" in entry_id:
            logger.warning("arXiv API error: %s", _clean(entry.get("summary", "")))
            return []

        paper_id = arxiv_id(entry_id)
        title = _clean(entry.get("title", ""))
        if not paper_id or not title:
            continue

        authors = ", ".join(
            a["name"] for a in entry.get("authors", []) if a.get("name")
        )

        try:
            items.append(
                NewsItem(
                    source="arxiv",
                    source_id=paper_id,
                    title=title,
                    # Versionless abs URL so it stays stable across revisions
                    url=f"https://arxiv.org/abs/{paper_id}",
                    author=authors or None,
                    content=_clean(entry.get("summary", "")) or None,
                    scraped_at=datetime.now(timezone.utc),
                )
            )
        except Exception as exc:
            logger.warning("Skipping arXiv entry %r: %s", entry_id, exc)

    return items


class ArxivScraper:
    """Most recently submitted papers in cs.AI, cs.CL and cs.LG."""

    source = "arxiv"

    def scrape(self, limit: int = 20) -> list[NewsItem]:
        try:
            response = requests.get(
                API_URL,
                params={
                    "search_query": SEARCH_QUERY,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                    "start": 0,
                    "max_results": limit,
                },
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning("arXiv request failed: %s", exc)
            return []

        return parse_feed(response.content, limit)
