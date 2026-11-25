"""Batch ingestion/enrichment entry point."""

import logging

from app.services.enrichment import run_enrichment
from app.services.indexing import run_indexing
from app.services.ingestion import run_ingestion


def run_pipeline() -> None:
    run_ingestion()
    run_enrichment()
    run_indexing()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # The OpenAI SDK's HTTP library logs every request at INFO.
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    run_pipeline()