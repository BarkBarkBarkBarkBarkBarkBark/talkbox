from src.application.services.kiosk_query_service import KioskQueryService
from src.infrastructure.config import settings


class FakeCategorizer:
    def __init__(self, category: str = "Food", error: Exception | None = None):
        self.category = category
        self.error = error

    def retrieve_category(self, query: str) -> str:
        if self.error:
            raise self.error
        return self.category


class FakeExecutor:
    def execute_query(self, category: str) -> dict:
        return {
            "results": {
                "type": "agencies",
                "category": category,
                "items_agencies": [
                    {
                        "name": "Community Pantry",
                        "phone": "916-555-0100",
                        "address": "1 Main St",
                        "description": "Emergency food",
                    }
                ],
            }
        }


class FakeHandler:
    def __init__(self, categorizer: FakeCategorizer | None = None):
        self.categorizer = categorizer or FakeCategorizer()
        self.executor = FakeExecutor()


class FakeAgencyRepository:
    def list_directory(self) -> list[dict]:
        return [
            {
                "name": "Community Pantry",
                "phone": "916-555-0100",
                "address": "1 Main St",
                "description": "Emergency food",
                "callable": True,
            }
        ]


def test_kiosk_queries_canonical_database_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(settings, "kiosk_mock_query", False)
    service = KioskQueryService(FakeHandler())

    result = service.query("food")

    assert result["search_mode"] == "category_vector_sql"
    assert [item["name"] for item in result["items"]] == ["Community Pantry"]


def test_kiosk_does_not_hide_database_errors_with_mock_data(monkeypatch) -> None:
    monkeypatch.setattr(settings, "kiosk_mock_query", False)
    service = KioskQueryService(FakeHandler(FakeCategorizer(error=RuntimeError("db down"))))

    result = service.query("food")

    assert result["empty"] is True
    assert result["search_mode"] == "database_error"
    assert result["items"] == []


def test_kiosk_directory_reads_canonical_database(monkeypatch) -> None:
    monkeypatch.setattr(settings, "kiosk_mock_query", False)
    service = KioskQueryService(FakeHandler(), agency_repository=FakeAgencyRepository())

    result = service.directory()

    assert result["search_mode"] == "database_directory"
    assert [item["name"] for item in result["items"]] == ["Community Pantry"]


def test_mock_catalog_requires_explicit_mock_mode(monkeypatch) -> None:
    monkeypatch.setattr(settings, "kiosk_mock_query", True)
    service = KioskQueryService(FakeHandler(FakeCategorizer(error=AssertionError("unused"))))

    result = service.query("I need food")

    assert result["search_mode"] == "mock"
    assert result["items"]