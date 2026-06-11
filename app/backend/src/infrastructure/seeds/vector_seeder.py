"""Load query-category seeds into the pgvector collection used by the router.

Seed payloads live as JSON under ``query_categories/``; each one becomes a
single LangChain ``Document`` with a deterministic id. ``PGVector.add_documents``
issues an upsert keyed on the id list, so re-running the seeder is idempotent.

A smart-skip short-circuits the whole thing when the collection already holds
at least as many rows as there are JSON seeds on disk, so a warm DB never
pays for an OpenAI round-trip at boot.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import psycopg2

from src.infrastructure.config import settings
from src.infrastructure.db import to_sync_dsn

logger = logging.getLogger(__name__)

SEEDS_DIR = Path(__file__).parent / "query_categories"


def _load_payloads() -> list[dict]:
    payloads: list[dict] = []
    for path in sorted(SEEDS_DIR.glob("*.json")):
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads


def _existing_count(collection_name: str) -> int:
    """Return the number of rows already in the collection, or 0 if the
    langchain_pg_* tables don't exist yet."""
    try:
        with psycopg2.connect(to_sync_dsn(settings.db_uri)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM langchain_pg_embedding e
                    JOIN langchain_pg_collection c ON e.collection_id = c.uuid
                    WHERE c.name = %s
                    """,
                    (collection_name,),
                )
                row = cur.fetchone()
                return int(row[0]) if row else 0
    except psycopg2.errors.UndefinedTable:
        return 0
    except psycopg2.Error as exc:
        logger.warning("count check failed, will attempt seed: %s", exc)
        return 0


def seed_query_categories() -> int:
    """Upsert all query-category seeds into PGVector. Returns the number written
    (0 if the collection was already fully populated)."""
    if not settings.db_uri:
        raise RuntimeError("DB_URI is required to seed the vector store.")

    payloads = _load_payloads()
    if not payloads:
        logger.warning("No seed documents found in %s", SEEDS_DIR)
        return 0

    existing = _existing_count(settings.collection_name)
    if existing >= len(payloads):
        logger.info(
            "skip seeding: collection '%s' already has %d >= %d rows",
            settings.collection_name,
            existing,
            len(payloads),
        )
        return 0

    # Only import here — skip path avoids pulling in LangChain and creating
    # provider clients altogether.
    from langchain_core.documents import Document
    from langchain_postgres import PGVector

    from src.infrastructure.llm.factory import get_embeddings

    documents = [
        Document(
            page_content=p["content"],
            metadata={"id": p["id"], "category": p["category"]},
        )
        for p in payloads
    ]

    store = PGVector(
        embeddings=get_embeddings(),
        collection_name=settings.collection_name,
        connection=settings.db_uri,
        use_jsonb=True,
    )
    store.add_documents(documents, ids=[d.metadata["id"] for d in documents])

    logger.info(
        "seeded %d documents into PGVector collection '%s' (was %d)",
        len(documents),
        settings.collection_name,
        existing,
    )
    return len(documents)
