from src.application.services.kiosk_query_service import KioskQueryService
from src.application.services.resource_sync_service import resource_sync_service
from src.infrastructure.config import settings
from src.infrastructure.fsc_resource_client import BootstrapSnapshot


class FakeResourceRetriever:
    def __init__(self, resource_ids: list[str] | None = None, error: Exception | None = None):
        self.resource_ids = resource_ids or []
        self.error = error

    def retrieve_resource_ids(self, query: str, limit: int = 9) -> list[str]:
        if self.error:
            raise self.error
        return self.resource_ids[:limit]


def test_kiosk_uses_vector_result_order(monkeypatch) -> None:
    monkeypatch.setattr(settings, "kiosk_mock_query", False)
    monkeypatch.setattr(settings, "resource_search_mode", "vector")
    monkeypatch.setattr(
        resource_sync_service,
        "_snapshot",
        BootstrapSnapshot.model_validate(
            {
                "content_version": 1,
                "services": [
                    {"id": "one", "name": "First", "category": "Food"},
                    {"id": "two", "name": "Second", "category": "Housing"},
                ],
            }
        ),
    )
    service = KioskQueryService(
        lambda: None,
        resource_retriever=FakeResourceRetriever(["two", "one"]),
    )

    result = service.query("somewhere to sleep")

    assert result["search_mode"] == "vector"
    assert [item["name"] for item in result["items"]] == ["Second", "First"]


def test_kiosk_reports_lexical_fallback_when_vector_search_fails(monkeypatch) -> None:
    monkeypatch.setattr(settings, "kiosk_mock_query", False)
    monkeypatch.setattr(settings, "resource_search_mode", "vector")
    monkeypatch.setattr(
        resource_sync_service,
        "_snapshot",
        BootstrapSnapshot.model_validate(
            {
                "content_version": 1,
                "services": [
                    {
                        "id": "one",
                        "name": "Community Pantry",
                        "category": "Food",
                        "description": "Emergency food assistance",
                    }
                ],
            }
        ),
    )
    service = KioskQueryService(
        lambda: None,
        resource_retriever=FakeResourceRetriever(error=RuntimeError("missing collection")),
    )

    result = service.query("food")

    assert result["search_mode"] == "lexical_fallback"
    assert [item["name"] for item in result["items"]] == ["Community Pantry"]