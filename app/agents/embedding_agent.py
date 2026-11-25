from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
# Max texts sent in one embeddings request.
EMBEDDING_BATCH_SIZE = 50

client = OpenAI()


def create_embedding(text: str) -> list[float]:
    """Generate an embedding vector for a piece of text using the OpenAI API."""

    return create_embeddings([text])[0]


def create_embeddings(
    texts: list[str], batch_size: int = EMBEDDING_BATCH_SIZE, openai_client=None
) -> list[list[float]]:
    """Embed many texts, sending up to batch_size texts per API request.

    Returns one embedding per input text, in the same order as texts.
    """
    openai_client = openai_client or client
    embeddings: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = openai_client.embeddings.create(
            model=EMBEDDING_MODEL, input=batch, dimensions=EMBEDDING_DIMENSIONS
        )
        # Each result carries the index of its input; sort so order never depends
        # on the order the API happens to return them in.
        ordered = sorted(response.data, key=lambda item: item.index)
        if len(ordered) != len(batch):
            raise ValueError(
                f"Expected {len(batch)} embeddings, got {len(ordered)}"
            )
        embeddings.extend(item.embedding for item in ordered)

    return embeddings
