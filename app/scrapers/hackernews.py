from datetime import datetime, timezone
import requests
import trafilatura

from app.schemas.news import NewsItem

TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"


def scrape_top_stories(limit: int = 5) -> list[NewsItem]:
    """Scrape the top Hacker News stories and normalize them into NewsItems."""

    story_ids = requests.get(TOP_STORIES_URL, timeout=10).json()

    news_items = []

    for story_id in story_ids:
        if len(news_items) >= limit:
            break

        story = requests.get(
            ITEM_URL.format(story_id),
            timeout=10
        ).json()

        url = story.get("url")
        title = story.get("title")

        # Some HN posts don't link to an external webpage
        if not url or not title:
            continue

        # Download webpage
        downloaded = trafilatura.fetch_url(url)

        if not downloaded:
            continue

        # Extract main article text
        content = trafilatura.extract(downloaded)

        if not content:
            continue

        news_items.append(
            NewsItem(
                source="hackernews",
                source_id=str(story_id),
                title=title,
                url=url,
                author=story.get("by"),
                content=content,
                scraped_at=datetime.now(timezone.utc),
            )
        )

    return news_items


if __name__ == "__main__":
    for item in scrape_top_stories():
        print(f"Scraped: {item.title}")