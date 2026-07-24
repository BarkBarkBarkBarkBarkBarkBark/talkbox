"""Build a fresh, versioned pgvector collection from canonical agency rows."""

from __future__ import annotations

from hashlib import sha256
import logging

import psycopg
from psycopg.rows import dict_row

from src.infrastructure.config import settings
from src.infrastructure.db import to_sync_dsn
from src.infrastructure.seeds.vector_seeder import existing_collection_count

logger = logging.getLogger(__name__)


def _document_content(agency: dict) -> str:
    fields = (
        ("Agency", agency["agency_name"]),
        ("Category", agency.get("category")),
        ("Description", agency.get("description")),
        ("Address", agency.get("address")),
        ("Insurance", agency.get("insurance")),
        ("Tags", agency.get("knowledge_tags")),
    )
    return "\n".join(f"{label}: {value.strip()}" for label, value in fields if value)


def _load_agencies() -> list[dict]:
    with psycopg.connect(to_sync_dsn(settings.db_uri), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.agency_name, a.phone_number, a.address,
                       a.description, a.insurance, a.knowledge_tags,
                       c.id AS category_id, c.name AS category
                FROM agencies a
                LEFT JOIN categories c ON c.id = a.category_id
                ORDER BY a.id
                """
            )
            return list(cur.fetchall())


def seed_agency_vectors() -> int:
    """Write all agencies to an empty versioned collection.

    Existing collections are never modified. Rotate ``AGENCY_COLLECTION_NAME``
    when agency content or the embedding model changes, validate the new
    collection, and switch readers separately.
    """
    if not settings.db_uri:
        raise RuntimeError("DB_URI is required to seed agency vectors.")

    collection_name = settings.agency_collection_name.strip()
    if not collection_name:
        raise RuntimeError("AGENCY_COLLECTION_NAME must not be empty.")

    existing = existing_collection_count(collection_name)
    if existing:
        raise RuntimeError(
            f"Collection {collection_name!r} already contains {existing} rows; "
            "rotate AGENCY_COLLECTION_NAME before rebuilding agency vectors."
        )

    agencies = _load_agencies()
    if not agencies:
        raise RuntimeError("Cannot seed agency vectors from an empty agencies table.")

    from langchain_core.documents import Document
    from langchain_postgres import PGVector

    from src.infrastructure.llm.factory import get_embeddings

    documents = []
    for agency in agencies:
        content = _document_content(agency)
        documents.append(
            Document(
                page_content=content,
                metadata={
                    "type": "agency",
                    "agency_id": agency["id"],
                    "category_id": agency.get("category_id"),
                    "category": agency.get("category"),
                    "content_sha256": sha256(content.encode("utf-8")).hexdigest(),
                    "embedding_model": settings.embeddings_model,
                },
            )
        )

    store = PGVector(
        embeddings=get_embeddings(),
        collection_name=collection_name,
        connection=settings.db_uri,
        use_jsonb=True,
    )
    store.add_documents(documents, ids=[str(agency["id"]) for agency in agencies])

    logger.info(
        "seeded %d agencies into fresh PGVector collection %r",
        len(documents),
        collection_name,
    )
    return len(documents)