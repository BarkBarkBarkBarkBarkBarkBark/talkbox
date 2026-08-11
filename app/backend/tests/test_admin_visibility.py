import os

os.environ.setdefault(
    "DB_URI", "postgresql+psycopg://talkbox:test@localhost:5432/talkbox"
)

from src.infrastructure import agency_repository
from src.infrastructure.sql_agent import sql_executor
from src.presentation import admin_routes
from src.presentation.auth import current_superuser
from src.presentation.schemas import AdminAgencyWrite


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def close(self):
        pass


def test_admin_agency_visibility_defaults_to_shown() -> None:
    agency = AdminAgencyWrite(agency="Community Pantry")
    assert agency.show_on_kiosk is True


def test_admin_agency_accepts_multiple_categories_and_legacy_category() -> None:
    multi = AdminAgencyWrite(
        agency="Community Pantry", categories=["Food", "Housing", "Food"]
    )
    legacy = AdminAgencyWrite(agency="Legacy Pantry", category="Food")

    assert multi.categories == ["Food", "Housing"]
    assert legacy.categories == ["Food"]


def test_import_visibility_is_optional_and_parses_hidden_values() -> None:
    legacy, legacy_errors = admin_routes._agency_from_values({"agency": "Legacy"})
    hidden, hidden_errors = admin_routes._agency_from_values(
        {"agency": "Hidden", "show_on_kiosk": "no"}
    )

    assert legacy_errors == []
    assert legacy["show_on_kiosk"] is True
    assert hidden_errors == []
    assert hidden["show_on_kiosk"] is False


def test_import_parses_semicolon_delimited_categories() -> None:
    row, errors = admin_routes._agency_from_values(
        {"agency": "Community Hub", "categories": "Food; Housing ;Food"}
    )

    assert errors == []
    assert row["categories"] == ["Food", "Housing", "Food"]


def test_directory_filters_hidden_rows(monkeypatch) -> None:
    cursor = FakeCursor(
        [("Visible Pantry", "9165550100", "1 Main St", "Emergency food")]
    )
    monkeypatch.setattr(
        agency_repository, "get_db_connection", lambda: FakeConnection(cursor)
    )

    items = agency_repository.AgencyRepository().list_directory()

    assert [item["name"] for item in items] == ["Visible Pantry"]
    assert "show_on_kiosk = TRUE" in cursor.executed[0][0]


def test_voice_sql_does_not_filter_hidden_rows(monkeypatch) -> None:
    cursor = FakeCursor(
        [
            (
                "Voice-only Pantry",
                "9165550100",
                "1 Main St",
                "Emergency food",
                None,
                None,
            )
        ]
    )
    monkeypatch.setattr(
        sql_executor, "get_db_connection", lambda: FakeConnection(cursor)
    )

    result = sql_executor.SQLExecutor().execute_query("Food")

    assert result["results"]["items_agencies"][0]["name"] == "Voice-only Pantry"
    assert "show_on_kiosk" not in cursor.executed[0][0]


def test_voice_sql_uses_multi_category_assignments(monkeypatch) -> None:
    cursor = FakeCursor(
        [
            (
                "Multi-service Center",
                "9165550100",
                "1 Main St",
                "Food and shelter",
                None,
                None,
            )
        ]
    )
    monkeypatch.setattr(
        sql_executor, "get_db_connection", lambda: FakeConnection(cursor)
    )

    result = sql_executor.SQLExecutor().execute_query("Food")

    assert result["results"]["items_agencies"][0]["name"] == "Multi-service Center"
    query = cursor.executed[0][0]
    assert "JOIN agency_categories" in query
    assert "SELECT DISTINCT" in query


def test_admin_mutations_require_superuser_dependency() -> None:
    mutation_routes = [
        route
        for route in admin_routes.router.routes
        if route.path.startswith("/agencies")
        and route.methods.intersection({"POST", "PATCH", "DELETE"})
    ]

    assert mutation_routes
    assert all(
        any(dependency.call is current_superuser for dependency in route.dependant.dependencies)
        for route in mutation_routes
    )
