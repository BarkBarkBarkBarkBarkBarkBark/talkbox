"""Public status and technician enrollment routes for physical kiosks."""

from __future__ import annotations

import hmac
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.infrastructure.config import settings
from src.presentation.kiosk_device_auth import (
    KioskDevice,
    device_connection,
    hash_secret,
    kiosk_device_status,
    new_credential,
    optional_kiosk_device,
    verify_secret,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kiosk/device", tags=["kiosk"])
_DEVICE_CODE_PATTERN = re.compile(r"^TB-[0-9]{3,}$")


class DeviceStatusResponse(BaseModel):
    enrolled: bool
    enabled: bool = False
    calling_enabled: bool = False
    device_code: str | None = None
    display_name: str | None = None
    location: str | None = None


class DeviceEnrollmentRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=512)
    display_name: str = Field(default="TalkBox kiosk", min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    device_code: str | None = Field(default=None, max_length=32)


def _status(device: KioskDevice | None) -> DeviceStatusResponse:
    return DeviceStatusResponse(
        enrolled=device is not None,
        enabled=bool(device and device.enabled),
        calling_enabled=bool(device and device.enabled and settings.kiosk_calling_enabled),
        device_code=device.device_code if device else None,
        display_name=device.display_name if device else None,
        location=device.location if device else None,
    )


def _normalize_device_code(device_code: str | None) -> str | None:
    if not device_code:
        return None
    normalized = device_code.strip().upper()
    if not _DEVICE_CODE_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=422, detail="Device code must use the TB-001 format.")
    return normalized


def _next_device_code(cur) -> str:
    cur.execute(
        """SELECT COALESCE(MAX(CAST(SUBSTRING(device_code FROM 4) AS INTEGER)), 0) + 1 AS next_code
           FROM kiosk_devices
           WHERE device_code ~ '^TB-[0-9]+$'"""
    )
    return f"TB-{int(cur.fetchone()['next_code']):03d}"


def _reusable_code_valid(code: str) -> bool:
    configured = settings.kiosk_reusable_enrollment_code
    return bool(
        settings.kiosk_reusable_enrollment_enabled
        and configured
        and hmac.compare_digest(code, configured)
    )


def _consume_one_time_code(cur, code: str) -> dict | None:
    cur.execute(
        """SELECT id, code_hash, device_code, display_name, location
           FROM kiosk_enrollment_codes
           WHERE used_at IS NULL AND expires_at > NOW()
           FOR UPDATE"""
    )
    for row in cur.fetchall():
        if verify_secret(code, row["code_hash"]):
            return row
    return None


@router.get("/status", response_model=DeviceStatusResponse)
def device_status(request: Request) -> DeviceStatusResponse:
    return _status(kiosk_device_status(request))


@router.post("/enroll", response_model=DeviceStatusResponse)
def enroll_device(payload: DeviceEnrollmentRequest, response: Response) -> DeviceStatusResponse:
    code = payload.code.strip()
    requested_code = _normalize_device_code(payload.device_code)
    reusable_code = _reusable_code_valid(code)
    credential = new_credential()
    device_id = uuid.uuid4()

    with device_connection() as conn, conn.cursor() as cur:
        enrollment = None if reusable_code else _consume_one_time_code(cur, code)
        if not reusable_code and enrollment is None:
            logger.warning("kiosk enrollment rejected: invalid or expired enrollment code")
            raise HTTPException(status_code=403, detail="Enrollment code is invalid or expired.")

        device_code = requested_code or (enrollment or {}).get("device_code") or _next_device_code(cur)
        display_name = (enrollment or {}).get("display_name") or payload.display_name.strip()
        location = (enrollment or {}).get("location") or payload.location
        try:
            cur.execute(
                """INSERT INTO kiosk_devices
                       (id, device_code, display_name, location, credential_hash, enabled, last_seen_at)
                   VALUES (%s, %s, %s, %s, %s, true, NOW())""",
                (device_id, device_code, display_name, location, hash_secret(credential)),
            )
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "23505":
                raise HTTPException(status_code=409, detail="Device code already exists.") from exc
            raise
        if enrollment:
            cur.execute(
                """UPDATE kiosk_enrollment_codes
                   SET used_at = NOW(), used_by_device_id = %s
                   WHERE id = %s AND used_at IS NULL""",
                (device_id, enrollment["id"]),
            )
            if cur.rowcount != 1:
                raise HTTPException(status_code=409, detail="Enrollment code has already been used.")

    response.set_cookie(
        key=settings.kiosk_device_cookie_name,
        value=credential,
        max_age=settings.kiosk_device_cookie_max_age_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.kiosk_device_cookie_samesite,
        path="/api/kiosk",
    )
    device = KioskDevice(
        id=device_id,
        device_code=device_code,
        display_name=display_name,
        location=location,
        enabled=True,
        revoked=False,
    )
    logger.info(
        "kiosk device enrolled: device=%s source=%s",
        device.device_code,
        "reusable" if reusable_code else "one_time",
    )
    return _status(device)