import os
import unittest
from types import SimpleNamespace
from unittest import mock

# connection.py calls create_engine() at import time; a dummy URL avoids needing
# a real database (create_engine doesn't connect until first use).
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:1/test")
# embedding_agent.py builds an OpenAI() client at import time; it is never called here.
os.environ.setdefault("OPENAI_API_KEY", "test-placeholder")

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.routes import search  # noqa: E402
from app.database import repository  # noqa: E402

EMBEDDING = [0.1, 0.2, 0.3]


class CapturingSession(Session):
    """A Session with no engine that records the query instead of running it."""

    def __init__(self):
        super().__init__()
        self.captured = None

    def query(self, *entities):
        query = super().query(*entities)
        session = self

        class Capturing(type(query)):
            def all(self):
                session.captured = self
                return []

        query.__class__ = Capturing
        return query


def compiled(query):
    return query.statement.compile(dialect=postgresql.dialect())


class RepositorySourceFilterTests(unittest.TestCase):
    def test_source_filter_uses_bound_parameter(self):
        db = CapturingSession()
        repository.search_similar_chunks(db, EMBEDDING, limit=5, source="arxiv'; DROP TABLE x;--")

        sql = compiled(db.captured)
        text = str(sql)
        self.assertIn("news_items.source = %(source_1)s", text)
        self.assertEqual(sql.params["source_1"], "arxiv'; DROP TABLE x;--")
        # The value is never interpolated into the SQL string
        self.assertNotIn("DROP TABLE", text)

    def test_no_source_means_no_filter(self):
        db = CapturingSession()
        repository.search_similar_chunks(db, EMBEDDING, limit=5)
        self.assertNotIn("news_items.source =", str(compiled(db.captured)))


class SearchRouteTests(unittest.TestCase):
    def fake_rows(self):
        chunk = SimpleNamespace(content="chunk text")
        item = SimpleNamespace(
            id=1, source="arxiv", title="A paper", url="https://arxiv.org/abs/2611.31240"
        )
        return [(chunk, item, -0.8)]

    def test_passes_source_and_returns_label(self):
        with mock.patch.object(search, "create_embedding", return_value=EMBEDDING), \
                mock.patch.object(
                    search, "search_similar_chunks", return_value=self.fake_rows()
                ) as fake_search:
            results = search.search_news(q="agents", limit=3, source="arxiv", db="db")

        fake_search.assert_called_once_with("db", EMBEDDING, limit=3, source="arxiv")
        self.assertEqual(results[0].source, "arxiv")
        self.assertAlmostEqual(results[0].similarity, 0.8)

    def test_source_defaults_to_none(self):
        with mock.patch.object(search, "create_embedding", return_value=EMBEDDING), \
                mock.patch.object(search, "search_similar_chunks", return_value=[]) as fake_search:
            search.search_news(q="agents", limit=5, source=None, db="db")

        self.assertIsNone(fake_search.call_args.kwargs["source"])


if __name__ == "__main__":
    unittest.main()
