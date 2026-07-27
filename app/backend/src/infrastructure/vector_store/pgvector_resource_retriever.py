"""Near-text retrieval for canonical FSC resources stored in pgvector."""

from __future__ import annotations

from collections.abc import Callable

from langchain_postgres import PGVector

from src.infrastructure.config import settings
from src.infrastructure.llm.factory import get_embeddings


class PGVectorResourceRetriever:
    def __init__(self, embeddings_factory: Callable | None = None) -> None:
        self._embeddings_factory = embeddings_factory or get_embeddings

    def retrieve_resource_ids(self, query: str, limit: int = 9) -> list[str]:
        if not settings.db_uri:
            raise RuntimeError("DB_URI is required for resource vector search.")
        if not settings.agency_collection_name.strip():
            raise RuntimeError("AGENCY_COLLECTION_NAME is required for resource vector search.")

        store = PGVector(
            embeddings=self._embeddings_factory(),
            collection_name=settings.agency_collection_name,
            connection=settings.db_uri,
            use_jsonb=True,
        )
        documents = store.similarity_search(query, k=limit)

        resource_ids: list[str] = []
        for document in documents:
            resource_id = document.metadata.get("resource_id")
            if resource_id is None:
                continue
            normalized_id = str(resource_id)
            if normalized_id not in resource_ids:
                resource_ids.append(normalized_id)
        return resource_ids