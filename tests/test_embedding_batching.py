import math
import os
import unittest
from types import SimpleNamespace
from unittest import mock

# connection.py calls create_engine() at import time; a dummy URL avoids needing
# a real database (create_engine doesn't connect until first use).
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:1/test")
# embedding_agent.py builds an OpenAI() client at import time; it is never called here.
os.environ.setdefault("OPENAI_API_KEY", "test-placeholder")

from app.agents import embedding_agent  # noqa: E402
from app.services import indexing  # noqa: E402


class FakeEmbeddingsClient:
    """Stands in for OpenAI(): records each embeddings.create call.

    Each text gets a unique vector, recorded in self.vectors so tests can check
    which text an embedding came from. Results come back in reverse order (with
    their index), so the code has to sort by index to match them to the right inputs.
    """

    def __init__(self):
        self.calls = []
        self.vectors = {}
        self.embeddings = SimpleNamespace(create=self._create)

    def _create(self, model, input, dimensions):
        texts = [input] if isinstance(input, str) else list(input)
        self.calls.append(texts)
        data = []
        for index, text in enumerate(texts):
            vector = self.vectors.setdefault(text, [float(len(self.vectors)), 0.5])
            data.append(SimpleNamespace(index=index, embedding=vector))
        return SimpleNamespace(data=list(reversed(data)))


class CreateEmbeddingsTest(unittest.TestCase):
    def test_batches_requests_and_keeps_input_order(self):
        fake = FakeEmbeddingsClient()
        texts = [f"chunk {n}" for n in range(120)]

        embeddings = embedding_agent.create_embeddings(texts, openai_client=fake)

        # 120 texts with a batch size of 50: 3 requests instead of 120.
        self.assertEqual(len(fake.calls), math.ceil(120 / embedding_agent.EMBEDDING_BATCH_SIZE))
        self.assertEqual([len(call) for call in fake.calls], [50, 50, 20])
        # Every text is sent exactly once, in order.
        self.assertEqual([t for call in fake.calls for t in call], texts)
        # Each embedding belongs to the text at the same position.
        self.assertEqual(embeddings, [fake.vectors[t] for t in texts])

    def test_empty_input_makes_no_requests(self):
        fake = FakeEmbeddingsClient()
        self.assertEqual(embedding_agent.create_embeddings([], openai_client=fake), [])
        self.assertEqual(fake.calls, [])

    def test_single_text_helper_still_works(self):
        fake = FakeEmbeddingsClient()
        with mock.patch.object(embedding_agent, "client", fake):
            vector = embedding_agent.create_embedding("hello")
        self.assertEqual(vector, fake.vectors["hello"])
        self.assertEqual(fake.calls, [["hello"]])


class RunIndexingTest(unittest.TestCase):
    def test_one_request_per_article_with_chunks_matched_in_order(self):
        fake = FakeEmbeddingsClient()
        # Small chunks so each article splits into several.
        long_item = SimpleNamespace(id=1, title="Long", content=" ".join(f"word{n}" for n in range(60)))
        short_item = SimpleNamespace(id=2, title="Short", content="just a few words here")
        inserted = {}

        def fake_insert(db, news_item_id, chunks):
            inserted[news_item_id] = chunks

        with (
            mock.patch.object(embedding_agent, "client", fake),
            mock.patch.object(indexing, "SessionLocal", mock.MagicMock),
            mock.patch.object(indexing, "get_unindexed_news_items", return_value=[long_item, short_item]),
            mock.patch.object(indexing, "insert_news_chunks", side_effect=fake_insert),
            # _chunk_text's max_tokens default is bound at definition time.
            mock.patch.object(indexing._chunk_text, "__defaults__", (10,)),
            mock.patch("builtins.print"),
        ):
            indexing.run_indexing()

        expected_long = indexing._chunk_text(long_item.content, max_tokens=10)
        expected_short = indexing._chunk_text(short_item.content, max_tokens=10)
        self.assertGreater(len(expected_long), 1)

        # One embeddings request per article, not one per chunk.
        self.assertEqual(fake.calls, [expected_long, expected_short])

        # Stored chunks are unchanged: same text, same order, right embedding each.
        for item_id, expected in ((1, expected_long), (2, expected_short)):
            self.assertEqual([c["content"] for c in inserted[item_id]], expected)
            self.assertEqual(
                [c["embedding"] for c in inserted[item_id]],
                [fake.vectors[text] for text in expected],
            )


if __name__ == "__main__":
    unittest.main()
