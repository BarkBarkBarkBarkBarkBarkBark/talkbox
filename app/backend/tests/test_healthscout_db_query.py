from src.infrastructure.healthscout_agent.healthscout_db_query import HealthScoutDB


def test_candidate_paths_prefers_explicit_env(monkeypatch):
    monkeypatch.setenv("HEALTHSCOUT_DB_PATH", "/var/task/database/custom.db")

    db = HealthScoutDB(db_name="sacramento")

    candidate_paths = db._candidate_paths()

    assert candidate_paths[0] == "/var/task/database/custom.db"
    assert candidate_paths[1] == "/data/sacramento.db"
    assert candidate_paths[2].endswith("/database/sacramento.db")
    assert candidate_paths[3] == "/app/database/sacramento.db"


def test_candidate_paths_uses_bundled_default_when_env_missing(monkeypatch):
    monkeypatch.delenv("HEALTHSCOUT_DB_PATH", raising=False)

    db = HealthScoutDB(db_name="sacramento")

    candidate_paths = db._candidate_paths()

    assert candidate_paths[0] == "/data/sacramento.db"
    assert candidate_paths[1].endswith("/database/sacramento.db")
    assert candidate_paths[2] == "/app/database/sacramento.db"
