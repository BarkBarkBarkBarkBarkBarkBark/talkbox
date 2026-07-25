"""Persistent storage for the validated FSC resource snapshot."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from src.infrastructure.fsc_resource_client import BootstrapSnapshot


class ResourceSnapshotCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> tuple[BootstrapSnapshot, datetime] | None:
        if not self.path.exists():
            return None
        with self._connect() as connection:
            self._create_schema(connection)
            row = connection.execute(
                "SELECT payload_json, fetched_at FROM resource_snapshot WHERE singleton_id = 1"
            ).fetchone()
        if row is None:
            return None
        return BootstrapSnapshot.model_validate_json(row[0]), datetime.fromisoformat(row[1])

    def save(self, snapshot: BootstrapSnapshot, fetched_at: datetime) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._create_schema(connection)
            connection.execute(
                """
                INSERT INTO resource_snapshot (
                    singleton_id,
                    schema_version,
                    content_version,
                    generated_at,
                    fetched_at,
                    payload_json
                ) VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(singleton_id) DO UPDATE SET
                    schema_version = excluded.schema_version,
                    content_version = excluded.content_version,
                    generated_at = excluded.generated_at,
                    fetched_at = excluded.fetched_at,
                    payload_json = excluded.payload_json
                """,
                (
                    snapshot.schema_version,
                    str(snapshot.content_version),
                    snapshot.generated_at.isoformat() if snapshot.generated_at else None,
                    fetched_at.isoformat(),
                    snapshot.model_dump_json(),
                ),
            )

    def quarantine(self) -> Path | None:
        if not self.path.exists():
            return None
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        quarantine_path = self.path.with_name(f"{self.path.name}.corrupt-{timestamp}")
        self.path.replace(quarantine_path)
        return quarantine_path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS resource_snapshot (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                schema_version TEXT NOT NULL,
                content_version TEXT NOT NULL,
                generated_at TEXT,
                fetched_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )