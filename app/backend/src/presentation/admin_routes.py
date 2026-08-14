"""Superuser-only agency resource management APIs."""

from __future__ import annotations

import csv
import io
import json
import logging
import secrets
import uuid
from datetime import datetime
from datetime import timedelta, timezone

import openpyxl
import psycopg
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

from src.infrastructure.config import settings
from src.infrastructure.db import to_sync_dsn
from src.infrastructure.persistence.database import User
from src.presentation.auth import current_superuser
from src.presentation.kiosk_device_auth import hash_secret
from src.presentation.schemas import (
    AdminAgencyPage,
    AdminAgencyRead,
    AdminAgencyBulkUpdate,
    AdminAgencyWrite,
    AdminCategoryRead,
    AdminImportPreview,
    AdminImportRow,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])

CANONICAL_COLUMNS = (
    "agency",
    "phone_number",
    "address",
    "categories",
    "description",
    "insurance",
    "knowledge_tags",
    "show_on_kiosk",
)
HEADER_ALIASES = {
    "agency": "agency",
    "agency_name": "agency",
    "organization": "agency",
    "organization_name": "agency",
    "name": "agency",
    "phone": "phone_number",
    "phone_number": "phone_number",
    "telephone": "phone_number",
    "address": "address",
    "location": "address",
    "category": "categories",
    "categories": "categories",
    "service_category": "categories",
    "service_type": "categories",
    "description": "description",
    "services": "description",
    "insurance": "insurance",
    "knowledge_tags": "knowledge_tags",
    "tags": "knowledge_tags",
    "show_on_kiosk": "show_on_kiosk",
    "show_in_browse": "show_on_kiosk",
    "visible": "show_on_kiosk",
}


class AdminKioskDeviceRead(BaseModel):
    id: uuid.UUID
    device_code: str
    display_name: str
    location: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None


class AdminDeviceEnrollmentCodeCreate(BaseModel):
    device_code: str | None = Field(default=None, max_length=32)
    display_name: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    label: str | None = Field(default=None, max_length=255)
    expires_in_seconds: int | None = Field(default=None, ge=60, le=86400)


class AdminDeviceEnrollmentCodeRead(BaseModel):
    code: str
    expires_at: datetime


class AdminKioskDeviceUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    enabled: bool | None = None
    revoke: bool = False


@router.get("/devices", response_model=list[AdminKioskDeviceRead])
def list_kiosk_devices(_: User = Depends(current_superuser)) -> list[AdminKioskDeviceRead]:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id, device_code, display_name, location, enabled,
                      created_at, updated_at, last_seen_at, revoked_at
               FROM kiosk_devices
               ORDER BY device_code"""
        )
        return cur.fetchall()


@router.post(
    "/devices/enrollment-codes",
    response_model=AdminDeviceEnrollmentCodeRead,
    status_code=201,
)
def create_device_enrollment_code(
    payload: AdminDeviceEnrollmentCodeCreate,
    user: User = Depends(current_superuser),
) -> AdminDeviceEnrollmentCodeRead:
    code = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=payload.expires_in_seconds or settings.kiosk_enrollment_code_ttl_seconds
    )
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO kiosk_enrollment_codes
                   (id, code_hash, device_code, display_name, location, label, created_by, expires_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                uuid.uuid4(),
                hash_secret(code),
                payload.device_code.strip().upper() if payload.device_code else None,
                payload.display_name,
                payload.location,
                payload.label,
                str(user.id),
                expires_at,
            ),
        )
        conn.commit()
    return AdminDeviceEnrollmentCodeRead(code=code, expires_at=expires_at)


@router.patch("/devices/{device_id}", response_model=AdminKioskDeviceRead)
def update_kiosk_device(
    device_id: uuid.UUID,
    payload: AdminKioskDeviceUpdate,
    _: User = Depends(current_superuser),
) -> AdminKioskDeviceRead:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE kiosk_devices
               SET display_name = COALESCE(%s, display_name),
                   location = COALESCE(%s, location),
                   enabled = CASE WHEN %s THEN false ELSE COALESCE(%s, enabled) END,
                   revoked_at = CASE WHEN %s THEN NOW() ELSE revoked_at END,
                   updated_at = NOW()
               WHERE id = %s
               RETURNING id, device_code, display_name, location, enabled,
                         created_at, updated_at, last_seen_at, revoked_at""",
            (
                payload.display_name,
                payload.location,
                payload.revoke,
                payload.enabled,
                payload.revoke,
                device_id,
            ),
        )
        device = cur.fetchone()
        if not device:
            raise HTTPException(status_code=404, detail="Kiosk device not found.")
        conn.commit()
    if payload.revoke:
        logger.info("kiosk device revoked: device=%s", device["device_code"])
    return device

def _connection():
    if not settings.db_uri:
        raise HTTPException(status_code=503, detail="Resource database is not configured.")
    return psycopg.connect(to_sync_dsn(settings.db_uri), row_factory=dict_row)


def _clean(value: object | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _agency_from_values(values: dict[str, object]) -> tuple[dict | None, list[str]]:
    row = {
        column: _clean(values.get(column))
        for column in CANONICAL_COLUMNS
        if column != "show_on_kiosk"
    }
    categories = _clean(values.get("categories"))
    row["categories"] = [
        category.strip() for category in (categories or "").split(";") if category.strip()
    ]
    raw_visibility = _clean(values.get("show_on_kiosk"))
    row["show_on_kiosk"] = (
        True
        if raw_visibility is None
        else raw_visibility.lower() not in {"0", "false", "no", "off", "hidden"}
    )
    errors = [] if row["agency"] else ["Agency name is required."]
    return (row if not errors else None, errors)


def _normalise_headers(headers: list[object]) -> tuple[dict[int, str], list[str]]:
    mapping: dict[int, str] = {}
    for index, header in enumerate(headers):
        normalised = _clean(header)
        if normalised:
            mapped = HEADER_ALIASES.get(normalised.lower().replace(" ", "_").replace("-", "_"))
            if mapped:
                mapping[index] = mapped
    errors = [] if "agency" in mapping.values() else ["No agency-name column was found."]
    return mapping, errors


def _parse_rows(filename: str, payload: bytes) -> tuple[list[tuple[int, dict | None, list[str]]], list[dict]]:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    source_errors: list[dict] = []
    try:
        if suffix == "csv":
            records = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))
        elif suffix in {"xlsx", "xlsm"}:
            workbook = openpyxl.load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
            records = list(workbook.active.iter_rows(values_only=True))
        else:
            return [], [{"message": "Upload a CSV or XLSX resource file."}]
    except (UnicodeDecodeError, csv.Error, openpyxl.utils.exceptions.InvalidFileException, OSError, ValueError) as exc:
        return [], [{"message": f"Could not read import file: {exc}"}]

    if not records:
        return [], [{"message": "The import file is empty."}]

    mapping, header_errors = _normalise_headers(list(records[0]))
    if header_errors:
        return [], [{"message": message} for message in header_errors]

    parsed = []
    for row_number, cells in enumerate(records[1:], start=2):
        values = {column: cells[index] if index < len(cells) else None for index, column in mapping.items()}
        row, errors = _agency_from_values(values)
        if any(_clean(value) for value in cells):
            parsed.append((row_number, row, errors))
    return parsed, source_errors


def _category_ids(cur, categories: list[str]) -> list[int]:
    category_ids = []
    for category in categories:
        cur.execute(
            """INSERT INTO categories (name) VALUES (%s)
               ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id""",
            (category,),
        )
        category_ids.append(cur.fetchone()["id"])
    return category_ids


def _replace_agency_categories(cur, agency_id: int, category_ids: list[int]) -> None:
    cur.execute("DELETE FROM agency_categories WHERE agency_id = %s", (agency_id,))
    if category_ids:
        cur.executemany(
            """INSERT INTO agency_categories (agency_id, category_id)
               VALUES (%s, %s) ON CONFLICT DO NOTHING""",
            [(agency_id, category_id) for category_id in category_ids],
        )


def _agency_select(where: str) -> str:
    return f"""
        SELECT a.id, a.agency_name AS agency, a.phone_number, a.address,
               COALESCE(
                   array_agg(c.name ORDER BY c.name) FILTER (WHERE c.id IS NOT NULL),
                   ARRAY[]::varchar[]
               ) AS categories,
               a.description, a.insurance, a.knowledge_tags, a.show_on_kiosk
        FROM agencies a
        LEFT JOIN agency_categories ac ON ac.agency_id = a.id
        LEFT JOIN categories c ON c.id = ac.category_id
        {where}
        GROUP BY a.id
    """


def _write_agency(cur, payload: AdminAgencyWrite, agency_id: int | None = None) -> dict:
    category_ids = _category_ids(cur, payload.categories)
    primary_category_id = category_ids[0] if category_ids else None
    values = (
        payload.agency,
        payload.phone_number,
        payload.address,
        primary_category_id,
        payload.description,
        payload.insurance,
        payload.knowledge_tags,
        payload.show_on_kiosk,
    )
    if agency_id is None:
        cur.execute(
            """INSERT INTO agencies
                   (agency_name, phone_number, address, category_id, description,
                    insurance, knowledge_tags, show_on_kiosk)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            values,
        )
        agency_id = cur.fetchone()["id"]
    else:
        cur.execute(
            """UPDATE agencies SET agency_name = %s, phone_number = %s, address = %s, category_id = %s,
               description = %s, insurance = %s, knowledge_tags = %s, show_on_kiosk = %s
               WHERE id = %s RETURNING id""",
            (*values, agency_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Resource not found.")
    _replace_agency_categories(cur, agency_id, category_ids)
    cur.execute(_agency_select("WHERE a.id = %s"), (agency_id,))
    return cur.fetchone()


@router.get("/agencies", response_model=AdminAgencyPage)
def list_agencies(
    search: str = "",
    category: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _: User = Depends(current_superuser),
) -> AdminAgencyPage:
    filters, values = [], []
    if search.strip():
        filters.append("(a.agency_name ILIKE %s OR a.address ILIKE %s OR a.description ILIKE %s)")
        values.extend([f"%{search.strip()}%"] * 3)
    if category:
        filters.append(
            """EXISTS (
                SELECT 1 FROM agency_categories ac_filter
                JOIN categories c_filter ON c_filter.id = ac_filter.category_id
                WHERE ac_filter.agency_id = a.id AND c_filter.name = %s
            )"""
        )
        values.append(category)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT count(*) AS total,
                       count(*) FILTER (WHERE a.show_on_kiosk) AS visible_total
                FROM agencies a {where}""",
            values,
        )
        counts = cur.fetchone()
        cur.execute(
            _agency_select(where) + " ORDER BY agency, id LIMIT %s OFFSET %s",
            (*values, page_size, (page - 1) * page_size),
        )
        items = cur.fetchall()
    return AdminAgencyPage(
        items=items,
        total=counts["total"],
        visible_total=counts["visible_total"],
        page=page,
        page_size=page_size,
    )


@router.get("/categories", response_model=list[AdminCategoryRead])
def list_categories(_: User = Depends(current_superuser)) -> list[AdminCategoryRead]:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT c.id, c.name, count(ac.agency_id)::int AS agency_count
               FROM categories c
               LEFT JOIN agency_categories ac ON ac.category_id = c.id
               GROUP BY c.id ORDER BY c.name"""
        )
        return cur.fetchall()


@router.post("/agencies", response_model=AdminAgencyRead, status_code=201)
def create_agency(payload: AdminAgencyWrite, _: User = Depends(current_superuser)) -> AdminAgencyRead:
    with _connection() as conn, conn.cursor() as cur:
        agency = _write_agency(cur, payload)
        conn.commit()
        return agency


@router.patch("/agencies/bulk")
def bulk_update_agencies(
    payload: AdminAgencyBulkUpdate, _: User = Depends(current_superuser)
) -> dict[str, int]:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM agencies WHERE id = ANY(%s) FOR UPDATE", (payload.ids,)
        )
        agency_ids = [row["id"] for row in cur.fetchall()]
        if len(agency_ids) != len(set(payload.ids)):
            raise HTTPException(status_code=404, detail="One or more resources were not found.")
        if payload.categories is not None:
            category_ids = _category_ids(cur, payload.categories)
            primary_category_id = category_ids[0] if category_ids else None
            cur.execute(
                "UPDATE agencies SET category_id = %s WHERE id = ANY(%s)",
                (primary_category_id, agency_ids),
            )
            for agency_id in agency_ids:
                _replace_agency_categories(cur, agency_id, category_ids)
        if payload.show_on_kiosk is not None:
            cur.execute(
                "UPDATE agencies SET show_on_kiosk = %s WHERE id = ANY(%s)",
                (payload.show_on_kiosk, agency_ids),
            )
        conn.commit()
    return {"updated": len(agency_ids)}


@router.patch("/agencies/{agency_id}", response_model=AdminAgencyRead)
def update_agency(agency_id: int, payload: AdminAgencyWrite, _: User = Depends(current_superuser)) -> AdminAgencyRead:
    with _connection() as conn, conn.cursor() as cur:
        agency = _write_agency(cur, payload, agency_id)
        conn.commit()
        return agency


@router.delete("/agencies/{agency_id}", status_code=204)
def delete_agency(agency_id: int, _: User = Depends(current_superuser)) -> None:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM agencies WHERE id = %s RETURNING id", (agency_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Resource not found.")
        conn.commit()


@router.get("/agencies/export")
def export_agencies(_: User = Depends(current_superuser)) -> StreamingResponse:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT a.agency_name AS agency, a.phone_number, a.address,
                      COALESCE(string_agg(c.name, ';' ORDER BY c.name), '') AS categories,
                      a.description, a.insurance, a.knowledge_tags, a.show_on_kiosk
               FROM agencies a
               LEFT JOIN agency_categories ac ON ac.agency_id = a.id
               LEFT JOIN categories c ON c.id = ac.category_id
               GROUP BY a.id ORDER BY a.agency_name"""
        )
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(cur.fetchall())
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=agencies_master.csv"})


@router.post("/imports", response_model=AdminImportPreview, status_code=201)
async def preview_import(
    file: UploadFile = File(...),
    user: User = Depends(current_superuser),
) -> AdminImportPreview:
    filename = file.filename or "resource-import"
    rows, errors = _parse_rows(filename, await file.read())
    valid_rows = sum(row is not None for _, row, _ in rows)
    invalid_rows = len(rows) - valid_rows
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO resource_import_batches (filename, status, total_rows, valid_rows, invalid_rows, errors, uploaded_by)
               VALUES (%s, 'previewed', %s, %s, %s, %s::json, %s) RETURNING id, created_at""",
            (filename, len(rows), valid_rows, invalid_rows, json.dumps(errors), user.id),
        )
        batch = cur.fetchone()
        for row_number, row, row_errors in rows:
            cur.execute(
                "INSERT INTO resource_import_rows (batch_id, row_number, data, errors) VALUES (%s, %s, %s::json, %s::json)",
                (batch["id"], row_number, json.dumps(row) if row else None, json.dumps(row_errors)),
            )
        conn.commit()
    return AdminImportPreview(id=batch["id"], filename=filename, status="previewed", total_rows=len(rows), valid_rows=valid_rows, invalid_rows=invalid_rows, errors=errors, created_at=batch["created_at"])


@router.get("/imports/{batch_id}", response_model=list[AdminImportRow])
def import_rows(batch_id: int, _: User = Depends(current_superuser)) -> list[AdminImportRow]:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT row_number, data, errors FROM resource_import_rows WHERE batch_id = %s ORDER BY row_number", (batch_id,))
        return cur.fetchall()


@router.post("/imports/{batch_id}/discard", response_model=AdminImportPreview)
def discard_import(batch_id: int, _: User = Depends(current_superuser)) -> AdminImportPreview:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE resource_import_batches SET status = 'discarded' WHERE id = %s AND status = 'previewed'
                     RETURNING id, filename, status, total_rows, valid_rows, invalid_rows, errors, created_at""", (batch_id,))
        batch = cur.fetchone()
        if not batch:
            raise HTTPException(status_code=404, detail="Preview not found or already finalized.")
        conn.commit()
        return batch


@router.post("/imports/{batch_id}/publish", response_model=AdminImportPreview)
def publish_import(batch_id: int, _: User = Depends(current_superuser)) -> AdminImportPreview:
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM resource_import_batches WHERE id = %s FOR UPDATE", (batch_id,))
        batch = cur.fetchone()
        if not batch or batch["status"] != "previewed":
            raise HTTPException(status_code=404, detail="Preview not found or already finalized.")
        if batch["total_rows"] == 0 or batch["invalid_rows"]:
            raise HTTPException(status_code=422, detail="Fix every import error before publishing.")
        cur.execute("SELECT data FROM resource_import_rows WHERE batch_id = %s ORDER BY row_number", (batch_id,))
        rows = [AdminAgencyWrite(**item["data"]) for item in cur.fetchall()]
        cur.execute("TRUNCATE agencies, categories RESTART IDENTITY CASCADE")
        for row in rows:
            _write_agency(cur, row)
        cur.execute("""UPDATE resource_import_batches SET status = 'published', published_at = %s WHERE id = %s
                     RETURNING id, filename, status, total_rows, valid_rows, invalid_rows, errors, created_at""", (datetime.now().astimezone(), batch_id))
        result = cur.fetchone()
        conn.commit()
        return result