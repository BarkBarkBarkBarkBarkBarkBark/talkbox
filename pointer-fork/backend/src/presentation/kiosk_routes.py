"""Kiosk-facing HTTP routes (keypad-first 6-inch UX).

All routes are additive and live under ``/api/kiosk``. They never touch the
existing ``/api/query`` or SMS behavior.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from src.application.services.kiosk_call_service import KioskCallService
from src.application.services.kiosk_query_service import KioskQueryService
from src.infrastructure.config import settings
from src.infrastructure.voice.twilio_voice_service import TwilioVoiceService
from src.presentation.routes import query_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kiosk", tags=["kiosk"])

_voice_service = TwilioVoiceService()
kiosk_query_service = KioskQueryService(query_handler)
kiosk_call_service = KioskCallService(_voice_service)

# ─── Pending browser-SDK calls ───────────────────────────────────────────────
# Maps identity (UUID str) → {"to": e164, "expires": epoch_float}
# Cleaned up by a background thread every 2 minutes.
_pending_calls: dict[str, dict] = {}
_pending_lock = threading.Lock()
_PENDING_TTL = 90  # seconds


def _prune_pending() -> None:
    now = time.time()
    with _pending_lock:
        expired = [k for k, v in _pending_calls.items() if v["expires"] < now]
        for k in expired:
            del _pending_calls[k]


def _schedule_prune() -> None:
    threading.Timer(120, lambda: (_prune_pending(), _schedule_prune())).start()


_schedule_prune()


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


class KioskVoiceTokenRequest(BaseModel):
    phone: str = Field(..., min_length=3, description="Number to call (must be allowlisted)")
    name: str | None = None


class KioskVoiceTokenResponse(BaseModel):
    token: str
    identity: str
    agency: str


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


# ─── Browser Voice SDK endpoints ──────────────────────────────────────────────

@router.post("/call/token", response_model=KioskVoiceTokenResponse)
def kiosk_call_token(payload: KioskVoiceTokenRequest) -> KioskVoiceTokenResponse:
    """Validate allowlist and issue a Twilio Voice access token for the browser SDK.

    The browser uses this token to initialise Device and connect() to Twilio.
    Twilio will then POST to /api/kiosk/call/twiml to get dial instructions.
    """
    from fastapi import HTTPException
    from src.application.services.kiosk_call_service import normalize_digits, to_e164

    if not _voice_service.browser_calling_configured:
        raise HTTPException(
            status_code=503,
            detail="Browser calling not configured. Set TWILIO_TWIML_APP_SID and TWILIO_PUBLIC_URL.",
        )

    phone_raw = payload.phone.strip()
    digits = normalize_digits(phone_raw)
    # Prefer E.164 pass-through for international numbers already starting with '+'
    if phone_raw.startswith("+"):
        e164 = f"+{digits}"
    else:
        e164 = to_e164(digits)

    if not e164:
        raise HTTPException(status_code=400, detail="Invalid phone number.")

    agency = kiosk_call_service.find_allowlisted_agency(digits)
    if agency is None:
        raise HTTPException(status_code=403, detail="Number not on approved call list.")

    identity = str(uuid.uuid4())
    with _pending_lock:
        _pending_calls[identity] = {
            "to": e164,
            "agency": agency,
            "expires": time.time() + _PENDING_TTL,
        }

    token = _voice_service.generate_access_token(identity=identity)
    logger.info("voice token issued: identity=%s agency=%s to=%s", identity, agency, e164)
    return KioskVoiceTokenResponse(token=token, identity=identity, agency=agency)


@router.post("/call/twiml")
async def kiosk_call_twiml(request: Request) -> Response:
    """Twilio webhook — return TwiML <Dial> for a validated pending call.

    Twilio POSTs here after the browser Device.connect() call is accepted.
    The SDK sends the identity as the 'From' field prefixed with 'client:'.
    """
    from twilio.twiml.voice_response import VoiceResponse

    form = await request.form()
    from_raw = str(form.get("From", "") or request.query_params.get("identity", ""))
    identity_key = from_raw.replace("client:", "").strip()

    with _pending_lock:
        pending = _pending_calls.get(identity_key)

    if not pending or pending["expires"] < time.time():
        logger.warning("twiml webhook: unknown/expired identity=%r", identity_key)
        vr = VoiceResponse()
        vr.say("This call could not be connected.")
        return Response(content=str(vr), media_type="application/xml")

    to_number = pending["to"]
    logger.info("twiml webhook: connecting identity=%s to=%s", identity_key, to_number)
    twiml = _voice_service.build_dial_twiml(to_number)
    return Response(content=twiml, media_type="application/xml")


@router.post("/call/status")
async def kiosk_call_status(request: Request) -> dict:
    """Twilio call lifecycle callback (ringing, in-progress, completed, failed)."""
    form = await request.form()
    sid = form.get("CallSid", "")
    status = form.get("CallStatus", "")
    to = form.get("To", "")
    duration = form.get("CallDuration", "")
    logger.info("twilio status callback: sid=%s status=%s to=%s duration=%ss", sid, status, to, duration)
    return {"received": True}


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
