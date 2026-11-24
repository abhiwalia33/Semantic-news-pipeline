import logging
from datetime import datetime, timezone
import requests
import trafilatura

from app.schemas.news import NewsItem

logger = logging.getLogger(__name__)

TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"


def _scrape_story(story_id: int) -> NewsItem | None:
    """Fetch one HN story and its linked article. Returns None if it has no usable content."""

    story = requests.get(
        ITEM_URL.format(story_id),
        timeout=10
    ).json()

    # Deleted/dead items come back as null
    if not story:
        return None

    url = story.get("url")
    title = story.get("title")

    # Some HN posts don't link to an external webpage
    if not url or not title:
        return None

    # Download webpage
    downloaded = trafilatura.fetch_url(url)

    if not downloaded:
        return None

    # Extract main article text
    content = trafilatura.extract(downloaded)

    if not content:
        return None

    return NewsItem(
        source="hackernews",
        source_id=str(story_id),
        title=title,
        url=url,
        author=story.get("by"),
        content=content,
        scraped_at=datetime.now(timezone.utc),
    )


def scrape_top_stories(limit: int = 30) -> list[NewsItem]:
    """Scrape the top Hacker News stories and normalize them into NewsItems."""

    story_ids = requests.get(TOP_STORIES_URL, timeout=10).json()

    news_items = []

    for story_id in story_ids:
        if len(news_items) >= limit:
            break

        try:
            item = _scrape_story(story_id)
        except Exception as exc:
            # One bad story/page shouldn't abort the whole run
            logger.warning("Skipping HN story %s: %s", story_id, exc)
            continue

        if item:
            news_items.append(item)

    return news_items


class HackerNewsScraper:
    """Scraper-interface adapter around scrape_top_stories()."""

    source = "hackernews"

    def scrape(self, limit: int) -> list[NewsItem]:
        return scrape_top_stories(limit)


if __name__ == "__main__":
    for item in scrape_top_stories():
        print(f"Scraped: {item.title}")