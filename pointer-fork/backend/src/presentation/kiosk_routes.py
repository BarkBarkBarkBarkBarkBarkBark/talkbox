"""Kiosk-facing HTTP routes (keypad-first 6-inch UX).

All routes are additive and live under ``/api/kiosk``. They never touch the
existing ``/api/query`` or SMS behavior. Calling is intentionally NOT exposed
here yet — Twilio Voice + an allowlist land in a later milestone (M6), so the
kiosk cannot dial anything from these endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.application.services.kiosk_call_service import KioskCallService
from src.application.services.kiosk_query_service import KioskQueryService
from src.infrastructure.config import settings
from src.infrastructure.voice.twilio_voice_service import TwilioVoiceService
from src.presentation.routes import query_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kiosk", tags=["kiosk"])

kiosk_query_service = KioskQueryService(query_handler)
kiosk_call_service = KioskCallService(TwilioVoiceService())


# ─── Schemas ─────────────────────────────────────────────────────────────────
class KioskQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Spoken or typed need")


class KioskItem(BaseModel):
    number: int
    name: str
    phone: str | None = None
    phone_display: str | None = None
    address: str | None = None
    description: str | None = None
    callable: bool = False


class KioskQueryResponse(BaseModel):
    category: str | None = None
    items: list[KioskItem] = Field(default_factory=list)
    empty: bool = False
    spoken_summary: str = ""
    fallback: KioskItem | None = None
    message: str | None = None


class KioskMenuItem(BaseModel):
    key: int
    action: str
    label: str
    query: str | None = None


class KioskConfigResponse(BaseModel):
    name: str
    mock_mode: bool
    idle_reset_seconds: int
    calling_enabled: bool
    menu: list[KioskMenuItem]


class KioskEventRequest(BaseModel):
    session_id: str | None = None
    event_type: str
    payload: dict | None = None


class KioskCallRequest(BaseModel):
    phone: str = Field(..., min_length=3, description="Number to call (must be allowlisted)")
    name: str | None = Field(default=None, description="Display name, for logging only")


class KioskCallResponse(BaseModel):
    allowed: bool
    status: str  # initiated | simulated | refused | failed
    agency: str | None = None
    sid: str | None = None
    reason: str | None = None


# Home menu — 1-9 number keys map to a quick category query or action.
_HOME_MENU: list[dict] = [
    {"key": 1, "action": "QUICK_QUERY", "label": "Shelter", "query": "I need shelter tonight"},
    {"key": 2, "action": "QUICK_QUERY", "label": "Food", "query": "I need food"},
    {"key": 3, "action": "QUICK_QUERY", "label": "Medical care", "query": "I need a doctor or clinic"},
    {"key": 4, "action": "QUICK_QUERY", "label": "Mental health", "query": "I need mental health help"},
    {"key": 5, "action": "QUICK_QUERY", "label": "Transportation", "query": "I need a ride"},
    {"key": 6, "action": "QUICK_QUERY", "label": "Veterans", "query": "I am a veteran and need help"},
    {"key": 7, "action": "QUICK_QUERY", "label": "Youth services", "query": "I am a young person and need help"},
    {"key": 8, "action": "VOICE_INPUT", "label": "Speak / type a need", "query": None},
    {"key": 9, "action": "CALL_211", "label": "Call 211 help line", "query": None},
]


# ─── Routes ──────────────────────────────────────────────────────────────────
@router.get("/config", response_model=KioskConfigResponse)
def kiosk_config() -> KioskConfigResponse:
    return KioskConfigResponse(
        name="Pointer",
        mock_mode=settings.kiosk_mock_query,
        idle_reset_seconds=settings.kiosk_idle_reset_seconds,
        # True only when KIOSK_CALLING_ENABLED=true and Twilio creds are set.
        # Even then, the backend dials allowlisted (database) numbers only.
        calling_enabled=kiosk_call_service.calling_enabled,
        menu=[KioskMenuItem(**m) for m in _HOME_MENU],
    )


@router.post("/query", response_model=KioskQueryResponse)
def kiosk_query(payload: KioskQueryRequest) -> KioskQueryResponse:
    logger.info("kiosk query: %r", payload.query)
    result = kiosk_query_service.query(payload.query)
    logger.info(
        "kiosk query result: category=%s items=%d empty=%s",
        result.get("category"),
        len(result.get("items") or []),
        result.get("empty"),
    )
    return KioskQueryResponse(**result)


@router.post("/call/start", response_model=KioskCallResponse)
def kiosk_call_start(payload: KioskCallRequest) -> KioskCallResponse:
    logger.info("kiosk call request: phone=%r name=%r", payload.phone, payload.name)
    result = kiosk_call_service.start_call(payload.phone)
    return KioskCallResponse(**result)


@router.post("/events", status_code=202)
def kiosk_events(event: KioskEventRequest) -> dict:
    # Event sink stub: log now, persist in a later milestone (kiosk_events table).
    logger.info(
        "kiosk event: type=%s session=%s payload=%s",
        event.event_type,
        event.session_id,
        event.payload,
    )
    return {"accepted": True}
