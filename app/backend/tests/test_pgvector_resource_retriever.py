from langchain_core.documents import Document

from src.infrastructure.config import settings
from src.infrastructure.vector_store import pgvector_resource_retriever


class FakeStore:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def similarity_search(self, query: str, k: int):
        assert query == "food for my family"
        assert k == 9
        return [
            Document(page_content="one", metadata={"resource_id": "resource-2"}),
            Document(page_content="duplicate", metadata={"resource_id": "resource-2"}),
            Document(page_content="legacy", metadata={"agency_id": 1}),
            Document(page_content="two", metadata={"resource_id": "resource-1"}),
        ]


def test_retriever_returns_unique_canonical_resource_ids(monkeypatch) -> None:
    monkeypatch.setattr(settings, "db_uri", "postgresql://database.example/test")
    monkeypatch.setattr(settings, "agency_collection_name", "agency_catalog_test")
    monkeypatch.setattr(pgvector_resource_retriever, "PGVector", FakeStore)
    retriever = pgvector_resource_retriever.PGVectorResourceRetriever(
        embeddings_factory=lambda: object()
    )

    result = retriever.retrieve_resource_ids("food for my family")

    assert result == ["resource-2", "resource-1"]