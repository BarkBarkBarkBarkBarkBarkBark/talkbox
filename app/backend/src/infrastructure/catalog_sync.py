"""Canonical catalog snapshot, push signal, and kiosk apply.

Fly/Neon is the publisher. A kiosk pulls the snapshot when catalog_meta.version
increases (admin "Push to kiosks").
"""

from __future__ import annotations

from datetime import datetime

from psycopg.rows import dict_row

from src.infrastructure.config import settings
from src.infrastructure.db import to_sync_dsn
import psycopg


def _connection():
    if not settings.db_uri:
        raise RuntimeError("DB_URI is not set")
    return psycopg.connect(to_sync_dsn(settings.db_uri), row_factory=dict_row)


def _ensure_meta(cur) -> None:
    cur.execute(
        "INSERT INTO catalog_meta (singleton_id, version) VALUES (1, 1) "
        "ON CONFLICT (singleton_id) DO NOTHING"
    )


def _iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def read_meta(cur) -> dict:
    _ensure_meta(cur)
    cur.execute(
        """SELECT version, updated_at, refresh_requested_at
           FROM catalog_meta WHERE singleton_id = 1"""
    )
    row = cur.fetchone()
    return {
        "content_version": int(row["version"]),
        "updated_at": _iso(row["updated_at"]),
        "pushed_at": _iso(row["refresh_requested_at"]),
    }


def build_snapshot(cur) -> dict:
    meta = read_meta(cur)
    cur.execute("SELECT id, name FROM categories ORDER BY id")
    categories = [{"id": row["id"], "name": row["name"]} for row in cur.fetchall()]
    cur.execute(
        """SELECT a.id, a.agency_name, a.phone_number, a.address, a.category_id,
                  a.description, a.insurance, a.knowledge_tags, a.show_on_kiosk,
                  COALESCE(
                      array_agg(c.name ORDER BY c.name) FILTER (WHERE c.id IS NOT NULL),
                      ARRAY[]::varchar[]
                  ) AS categories
           FROM agencies a
           LEFT JOIN agency_categories ac ON ac.agency_id = a.id
           LEFT JOIN categories c ON c.id = ac.category_id
           GROUP BY a.id
           ORDER BY a.id"""
    )
    agencies = []
    for row in cur.fetchall():
        agencies.append(
            {
                "id": row["id"],
                "agency": row["agency_name"],
                "phone_number": row["phone_number"],
                "address": row["address"],
                "category_id": row["category_id"],
                "description": row["description"],
                "insurance": row["insurance"],
                "knowledge_tags": row["knowledge_tags"],
                "show_on_kiosk": bool(row["show_on_kiosk"]),
                "categories": list(row["categories"] or []),
            }
        )
    cur.execute(
        "SELECT agency_id, category_id FROM agency_categories ORDER BY agency_id, category_id"
    )
    assignments = [
        {"agency_id": row["agency_id"], "category_id": row["category_id"]}
        for row in cur.fetchall()
    ]
    visible = sum(1 for agency in agencies if agency["show_on_kiosk"])
    return {
        **meta,
        "agency_count": len(agencies),
        "visible_count": visible,
        "categories": categories,
        "agencies": agencies,
        "assignments": assignments,
    }


def bump_push(cur) -> dict:
    _ensure_meta(cur)
    cur.execute(
        """UPDATE catalog_meta
           SET version = version + 1,
               updated_at = now(),
               refresh_requested_at = now()
           WHERE singleton_id = 1
           RETURNING version, updated_at, refresh_requested_at"""
    )
    row = cur.fetchone()
    snapshot = build_snapshot(cur)
    snapshot["content_version"] = int(row["version"])
    snapshot["updated_at"] = _iso(row["updated_at"])
    snapshot["pushed_at"] = _iso(row["refresh_requested_at"])
    return snapshot


def apply_snapshot(cur, snapshot: dict) -> dict:
    categories = snapshot.get("categories") or []
    agencies = snapshot.get("agencies") or []
    assignments = snapshot.get("assignments")
    version = int(snapshot["content_version"])
    if not agencies:
        raise ValueError("Catalog snapshot contains no agencies")

    if assignments is None:
        name_to_id = {row["name"]: row["id"] for row in categories}
        assignments = []
        for agency in agencies:
            for name in agency.get("categories") or []:
                category_id = name_to_id.get(name)
                if category_id is not None:
                    assignments.append(
                        {"agency_id": agency["id"], "category_id": category_id}
                    )

    cur.execute("DELETE FROM agency_categories")
    cur.execute("DELETE FROM agencies")
    cur.execute("DELETE FROM categories")

    if categories:
        cur.executemany(
            "INSERT INTO categories (id, name) VALUES (%s, %s)",
            [(row["id"], row["name"]) for row in categories],
        )
    if agencies:
        cur.executemany(
            """INSERT INTO agencies
                   (id, agency_name, phone_number, address, category_id, description,
                    insurance, knowledge_tags, show_on_kiosk)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [
                (
                    row["id"],
                    row["agency"],
                    row.get("phone_number"),
                    row.get("address"),
                    row.get("category_id"),
                    row.get("description"),
                    row.get("insurance"),
                    row.get("knowledge_tags"),
                    bool(row.get("show_on_kiosk", True)),
                )
                for row in agencies
            ],
        )
    if assignments:
        cur.executemany(
            "INSERT INTO agency_categories (agency_id, category_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            [(row["agency_id"], row["category_id"]) for row in assignments],
        )

    cur.execute(
        "SELECT setval(pg_get_serial_sequence('categories', 'id'), COALESCE((SELECT MAX(id) FROM categories), 1), true)"
    )
    cur.execute(
        "SELECT setval(pg_get_serial_sequence('agencies', 'id'), COALESCE((SELECT MAX(id) FROM agencies), 1), true)"
    )

    _ensure_meta(cur)
    cur.execute(
        """UPDATE catalog_meta
           SET version = %s, updated_at = now()
           WHERE singleton_id = 1""",
        (version,),
    )
    visible = sum(1 for row in agencies if row.get("show_on_kiosk", True))
    return {
        "content_version": version,
        "agency_count": len(agencies),
        "visible_count": visible,
        "pushed_at": snapshot.get("pushed_at"),
    }


def load_snapshot() -> dict:
    with _connection() as conn, conn.cursor() as cur:
        return build_snapshot(cur)


def load_version() -> dict:
    with _connection() as conn, conn.cursor() as cur:
        return read_meta(cur)


def push_catalog() -> dict:
    with _connection() as conn, conn.cursor() as cur:
        snapshot = bump_push(cur)
        conn.commit()
        return {
            "content_version": snapshot["content_version"],
            "updated_at": snapshot["updated_at"],
            "pushed_at": snapshot["pushed_at"],
            "agency_count": snapshot["agency_count"],
            "visible_count": snapshot["visible_count"],
        }


def replace_local_catalog(snapshot: dict) -> dict:
    with _connection() as conn, conn.cursor() as cur:
        result = apply_snapshot(cur, snapshot)
        conn.commit()
        return result
