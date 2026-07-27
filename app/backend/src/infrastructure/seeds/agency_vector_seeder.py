"""Build a fresh, versioned pgvector collection from canonical FSC resources."""

from __future__ import annotations

import asyncio
from hashlib import sha256
import logging

from src.infrastructure.config import settings
from src.infrastructure.fsc_resource_client import BootstrapSnapshot, FSCResourceClient
from src.infrastructure.seeds.vector_seeder import existing_collection_count

logger = logging.getLogger(__name__)


def _document_content(resource: dict) -> str:
    fields = (
        ("Resource", resource["name"]),
        ("Organization", resource.get("organization_name")),
        ("Category", resource.get("category")),
        ("Description", resource.get("description")),
        ("Address", resource.get("address")),
        ("City", resource.get("city")),
        ("Eligibility", resource.get("eligibility_text")),
        ("Languages", resource.get("languages_text")),
        ("Hours", resource.get("hours_text")),
    )
    return "\n".join(f"{label}: {value.strip()}" for label, value in fields if value)


async def _load_snapshot() -> BootstrapSnapshot:
    if not settings.fsc_resource_api_base_url or not settings.fsc_resource_api_key:
        raise RuntimeError(
            "FSC_RESOURCE_API_BASE_URL and FSC_RESOURCE_API_KEY are required "
            "to seed canonical resource vectors."
        )
    client = FSCResourceClient(
        settings.fsc_resource_api_base_url,
        settings.fsc_resource_api_key,
        settings.fsc_resource_request_timeout_seconds,
    )
    try:
        version = await client.get_version()
        snapshot = await client.get_bootstrap()
    finally:
        await client.close()
    if snapshot.content_version != version.content_version:
        raise RuntimeError("Bootstrap content version does not match version endpoint.")
    return snapshot


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

    snapshot = asyncio.run(_load_snapshot())
    resources = [
        service
        for service in snapshot.services
        if service.talkbox_visible
        and (
            not service.status
            or service.status.lower() in {"active", "published", "approved"}
        )
    ]
    if not resources:
        raise RuntimeError("Cannot seed agency vectors from an empty FSC snapshot.")

    from langchain_core.documents import Document
    from langchain_postgres import PGVector

    from src.infrastructure.llm.factory import get_embeddings

    documents = []
    for resource in resources:
        content = _document_content(resource.model_dump(mode="json"))
        documents.append(
            Document(
                page_content=content,
                metadata={
                    "type": "resource",
                    "resource_id": str(resource.id),
                    "category": resource.category,
                    "content_version": snapshot.content_version,
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
    store.add_documents(documents, ids=[str(resource.id) for resource in resources])

    logger.info(
        "seeded %d canonical resources into fresh PGVector collection %r",
        len(documents),
        collection_name,
    )
    return len(documents)