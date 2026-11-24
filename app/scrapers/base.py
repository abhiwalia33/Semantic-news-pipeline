# Base scraper interface
from typing import Protocol

from app.schemas.news import NewsItem


class Scraper(Protocol):
    """Common interface every news source implements.

    `source` is the label stored on each NewsItem; together with `source_id`
    it is the de-duplication key in the database, so it must be stable and
    unique per source.
    """

    source: str

    def scrape(self, limit: int) -> list[NewsItem]:
        """Return up to `limit` normalized NewsItems from this source."""
        ...
