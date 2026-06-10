"""Seed the ``categories`` + ``agencies`` tables from the master CSV.

The CSV lives alongside this module (``agencies_master.csv``) so it ships
inside the backend image. Callers (CLI, bootstrap entrypoint) invoke
``seed_agencies()`` without arguments; operators can override the CSV path
explicitly if they need to pilot a different dataset.

Strategy: TRUNCATE + INSERT inside a single transaction. Idempotent —
re-running replaces the contents.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import psycopg2

from src.infrastructure.config import settings
from src.infrastructure.db import to_sync_dsn

logger = logging.getLogger(__name__)

DEFAULT_CSV_PATH = Path(__file__).parent / "agencies_master.csv"

EXPECTED_COLUMNS = {
    "agency",
    "phone_number",
    "address",
    "category",
    "description",
    "insurance",
    "knowledge_tags",
}


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    return v or None


def seed_agencies(csv_path: Path | None = None) -> tuple[int, int]:
    """Replace categories + agencies with rows from ``csv_path``.

    Returns ``(categories_inserted, agencies_inserted)``.
    """
    if not settings.db_uri:
        raise RuntimeError("DB_URI is required to seed agencies.")

    path = csv_path or DEFAULT_CSV_PATH
    if not path.exists():
        raise FileNotFoundError(f"Agencies CSV not found: {path}")

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = EXPECTED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing columns: {sorted(missing)}")
        rows = [row for row in reader]

    if not rows:
        logger.warning("No rows in %s", path)
        return (0, 0)

    # Unique categories preserving insertion order for deterministic ids.
    categories: list[str] = []
    seen: set[str] = set()
    for row in rows:
        cat = _norm(row.get("category"))
        if cat and cat not in seen:
            seen.add(cat)
            categories.append(cat)

    with psycopg2.connect(to_sync_dsn(settings.db_uri)) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE agencies, categories RESTART IDENTITY CASCADE")

            cur.executemany(
                "INSERT INTO categories (name) VALUES (%s)",
                [(c,) for c in categories],
            )

            cur.execute("SELECT id, name FROM categories")
            category_id_by_name = {name: cid for cid, name in cur.fetchall()}

            agency_rows = []
            for row in rows:
                agency_name = _norm(row.get("agency"))
                if not agency_name:
                    continue
                cat = _norm(row.get("category"))
                agency_rows.append(
                    (
                        agency_name,
                        _norm(row.get("phone_number")),
                        _norm(row.get("address")),
                        category_id_by_name.get(cat) if cat else None,
                        _norm(row.get("description")),
                        _norm(row.get("insurance")),
                        _norm(row.get("knowledge_tags")),
                    )
                )

            cur.executemany(
                """
                INSERT INTO agencies
                    (agency_name, phone_number, address, category_id,
                     description, insurance, knowledge_tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                agency_rows,
            )
        conn.commit()

    logger.info(
        "seeded %d categories and %d agencies from %s",
        len(categories),
        len(agency_rows),
        path.name,
    )
    return (len(categories), len(agency_rows))
