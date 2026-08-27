import os

os.environ.setdefault(
    "DB_URI", "postgresql+psycopg://talkbox:test@localhost:5432/talkbox"
)

from src.infrastructure.catalog_sync import apply_snapshot, bump_push, build_snapshot, read_meta


class FakeCursor:
    def __init__(self, meta=None, categories=None, agencies=None, assignments=None):
        self.meta = meta or {
            "version": 1,
            "updated_at": None,
            "refresh_requested_at": None,
        }
        self.categories = list(categories or [])
        self.agencies = list(agencies or [])
        self.assignments = list(assignments or [])
        self.executed = []
        self._fetch = None

    def execute(self, query, params=None):
        self.executed.append((query, params))
        sql = " ".join(query.split())
        if sql.startswith("INSERT INTO catalog_meta"):
            self._fetch = None
        elif "FROM catalog_meta" in sql and "UPDATE" not in sql:
            self._fetch = {
                "version": self.meta["version"],
                "updated_at": self.meta["updated_at"],
                "refresh_requested_at": self.meta["refresh_requested_at"],
            }
        elif sql.startswith("UPDATE catalog_meta") and "RETURNING" in sql:
            self.meta["version"] = int(self.meta["version"]) + 1
            self.meta["refresh_requested_at"] = "now"
            self.meta["updated_at"] = "now"
            self._fetch = {
                "version": self.meta["version"],
                "updated_at": self.meta["updated_at"],
                "refresh_requested_at": self.meta["refresh_requested_at"],
            }
        elif sql.startswith("SELECT id, name FROM categories"):
            self._fetch = self.categories
        elif "FROM agencies a" in sql:
            self._fetch = self.agencies
        elif sql.startswith("SELECT agency_id, category_id"):
            self._fetch = self.assignments
        elif sql.startswith("DELETE FROM"):
            self._fetch = None
        else:
            self._fetch = None

    def executemany(self, query, params):
        self.executed.append((query, list(params)))

    def fetchone(self):
        if isinstance(self._fetch, list):
            return self._fetch[0] if self._fetch else None
        return self._fetch

    def fetchall(self):
        if isinstance(self._fetch, list):
            return self._fetch
        return [self._fetch] if self._fetch is not None else []


def test_read_meta_returns_version():
    cursor = FakeCursor(meta={"version": 4, "updated_at": None, "refresh_requested_at": None})
    assert read_meta(cursor)["content_version"] == 4


def test_build_snapshot_includes_visibility_and_joins():
    cursor = FakeCursor(
        categories=[{"id": 1, "name": "Housing"}],
        agencies=[
            {
                "id": 9,
                "agency_name": "Shelter",
                "phone_number": "211",
                "address": None,
                "category_id": 1,
                "description": None,
                "insurance": None,
                "knowledge_tags": None,
                "show_on_kiosk": False,
                "categories": ["Housing"],
            }
        ],
        assignments=[{"agency_id": 9, "category_id": 1}],
    )
    snapshot = build_snapshot(cursor)
    assert snapshot["agency_count"] == 1
    assert snapshot["visible_count"] == 0
    assert snapshot["agencies"][0]["agency"] == "Shelter"
    assert snapshot["agencies"][0]["show_on_kiosk"] is False
    assert snapshot["assignments"] == [{"agency_id": 9, "category_id": 1}]


def test_bump_push_increments_version():
    cursor = FakeCursor(agencies=[], categories=[], assignments=[])
    # bump_push calls build_snapshot which needs agencies; empty list is ok for bump itself
    # but apply requires agencies. bump_push should still increment.
    cursor.agencies = [
        {
            "id": 1,
            "agency_name": "A",
            "phone_number": None,
            "address": None,
            "category_id": None,
            "description": None,
            "insurance": None,
            "knowledge_tags": None,
            "show_on_kiosk": True,
            "categories": [],
        }
    ]
    result = bump_push(cursor)
    assert result["content_version"] == 2
    assert result["pushed_at"] == "now"


def test_apply_snapshot_replaces_catalog_and_records_version():
    cursor = FakeCursor()
    result = apply_snapshot(
        cursor,
        {
            "content_version": 7,
            "pushed_at": "2026-08-26T00:00:00+00:00",
            "categories": [{"id": 1, "name": "Housing"}],
            "agencies": [
                {
                    "id": 3,
                    "agency": "Hidden House",
                    "phone_number": None,
                    "address": None,
                    "category_id": 1,
                    "description": None,
                    "insurance": None,
                    "knowledge_tags": None,
                    "show_on_kiosk": False,
                    "categories": ["Housing"],
                }
            ],
            "assignments": [{"agency_id": 3, "category_id": 1}],
        },
    )
    deletes = [sql for sql, _ in cursor.executed if sql.strip().startswith("DELETE")]
    assert any("agency_categories" in sql for sql in deletes)
    assert any("agencies" in sql for sql in deletes)
    assert result["content_version"] == 7
    assert result["visible_count"] == 0
    assert result["agency_count"] == 1


def test_apply_snapshot_rejects_empty_catalog():
    cursor = FakeCursor()
    try:
        apply_snapshot(cursor, {"content_version": 1, "agencies": []})
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "no agencies" in str(exc)
