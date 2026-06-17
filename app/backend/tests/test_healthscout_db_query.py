from pathlib import Path

from src.infrastructure.healthscout_agent.healthscout_db_query import HealthScoutDB


def test_candidate_paths_prefers_explicit_env(monkeypatch):
    monkeypatch.setenv("HEALTHSCOUT_DB_PATH", "/var/task/database/custom.db")

    db = HealthScoutDB(db_name="sacramento")

    assert db._candidate_paths() == (
        "/var/task/database/custom.db",
        "/data/sacramento.db",
        str(Path(__file__).resolve().parents[2] / "database" / "sacramento.db"),
        "/app/database/sacramento.db",
    )


def test_candidate_paths_uses_bundled_default_when_env_missing(monkeypatch):
    monkeypatch.delenv("HEALTHSCOUT_DB_PATH", raising=False)

    db = HealthScoutDB(db_name="sacramento")

    assert db._candidate_paths() == (
        "/data/sacramento.db",
        str(Path(__file__).resolve().parents[2] / "database" / "sacramento.db"),
        "/app/database/sacramento.db",
    )
