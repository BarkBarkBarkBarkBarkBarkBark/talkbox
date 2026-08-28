"""Authentication primitives for physical TalkBox devices.

This is intentionally separate from the fastapi-users administration session.
Each kiosk receives an opaque browser cookie whose secret is stored only as a
slow hash in the database and can be revoked one device at a time.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import uuid
from dataclasses import dataclass

import psycopg
from fastapi import HTTPException, Request
from psycopg.rows import dict_row

from src.infrastructure.config import settings
from src.infrastructure.db import to_sync_dsn

logger = logging.getLogger(__name__)

_HASH_PREFIX = "scrypt"
_SALT_BYTES = 16


@dataclass(frozen=True)
class KioskDevice:
    id: uuid.UUID
    device_code: str
    display_name: str
    location: str | None
    enabled: bool
    revoked: bool


# The Pi appliance browser hits FastAPI via nginx as Host: localhost.
# Fleet enrollment cookies are for remote kiosks; this machine is the kiosk.
LOCAL_APPLIANCE = KioskDevice(
    id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    device_code="TB-LOCAL",
    display_name="Local appliance",
    location="localhost",
    enabled=True,
    revoked=False,
)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}


def is_local_appliance(request: Request) -> bool:
    host = (request.headers.get("host") or "").split(":")[0].strip().lower()
    return host in _LOCAL_HOSTS


def new_credential() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(secret: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(
        secret.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32
    )
    return "$".join(
        (
            _HASH_PREFIX,
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(derived).decode("ascii"),
        )
    )


def verify_secret(secret: str, encoded_hash: str) -> bool:
    try:
        algorithm, salt_b64, expected_b64 = encoded_hash.split("$", 2)
        if algorithm != _HASH_PREFIX:
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(expected_b64.encode("ascii"))
        actual = hashlib.scrypt(
            secret.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=len(expected)
        )
    except (ValueError, UnicodeEncodeError):
        return False
    return hmac.compare_digest(actual, expected)


def device_connection():
    if not settings.db_uri:
        raise HTTPException(status_code=503, detail="Device database is not configured.")
    return psycopg.connect(to_sync_dsn(settings.db_uri), row_factory=dict_row)


def _credential_from_request(request: Request) -> str | None:
    credential = request.cookies.get(settings.kiosk_device_cookie_name)
    if not credential or len(credential) > 512:
        return None
    return credential


def _find_device(credential: str, include_inactive: bool = False) -> KioskDevice | None:
    with device_connection() as conn, conn.cursor() as cur:
        # Credentials use an independent salt per device, so an intentionally
        # small fleet is checked one row at a time without storing lookup keys.
        query = """SELECT id, device_code, display_name, location, credential_hash,
                          enabled, revoked_at, last_seen_at
                   FROM kiosk_devices"""
        if not include_inactive:
            query += " WHERE enabled = true AND revoked_at IS NULL"
        cur.execute(query)
        for row in cur.fetchall():
            if not verify_secret(credential, row["credential_hash"]):
                continue
            if row["enabled"] and row["revoked_at"] is None:
                cur.execute(
                    """UPDATE kiosk_devices
                       SET last_seen_at = NOW(), updated_at = NOW()
                       WHERE id = %s
                         AND (
                           last_seen_at IS NULL
                           OR last_seen_at < NOW() - (%s * INTERVAL '1 second')
                         )""",
                    (row["id"], settings.kiosk_device_last_seen_interval_seconds),
                )
            return KioskDevice(
                id=row["id"],
                device_code=row["device_code"],
                display_name=row["display_name"],
                location=row["location"],
                enabled=row["enabled"],
                revoked=row["revoked_at"] is not None,
            )
    return None


def optional_kiosk_device(request: Request) -> KioskDevice | None:
    credential = _credential_from_request(request)
    if credential is None:
        return None
    device = _find_device(credential)
    if device is None:
        logger.warning("kiosk device access rejected: invalid, disabled, or revoked credential")
    return device


def require_kiosk_device(request: Request) -> KioskDevice:
    device = optional_kiosk_device(request)
    if device is not None:
        return device
    if settings.kiosk_calling_enabled and is_local_appliance(request):
        return LOCAL_APPLIANCE
    raise HTTPException(
        status_code=403,
        detail="Phone calling is available on enrolled TalkBox kiosks.",
    )


def kiosk_device_status(request: Request) -> KioskDevice | None:
    credential = _credential_from_request(request)
    device = _find_device(credential, include_inactive=True) if credential else None
    if device is not None:
        return device
    if settings.kiosk_calling_enabled and is_local_appliance(request):
        return LOCAL_APPLIANCE
    return None