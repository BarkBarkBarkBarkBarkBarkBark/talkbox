"""Kiosk Twilio calling routes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse

from src.application.services.kiosk_call_service import (
    KioskCallService,
    expand_short_code,
    normalize_digits,
    to_e164,
)
from src.infrastructure.config import settings
from src.infrastructure.voice.twilio_voice_service import TwilioVoiceService
from src.presentation.kiosk_device_auth import KioskDevice, require_kiosk_device

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kiosk", tags=["kiosk"])

_voice_service = TwilioVoiceService()
kiosk_call_service = KioskCallService(_voice_service)

_IDENTITY_TOKEN_TTL_SECONDS = 90
_PENDING_CALLS: dict[str, dict] = {}
_LAST_TOKEN_REQUEST: dict[str, float] = {}


class KioskCallRequest(BaseModel):
    phone: str = Field(
        ...,
        min_length=3,
        description="Number to call (must be allowlisted)",
    )
    name: str | None = Field(default=None, description="Display name, for logging only")


class KioskCallResponse(BaseModel):
    allowed: bool
    status: str
    agency: str | None = None
    sid: str | None = None
    reason: str | None = None


class KioskVoiceTokenRequest(BaseModel):
    phone: str = Field(
        ...,
        min_length=3,
        description="Number to call (must be allowlisted)",
    )
    name: str | None = None


class KioskVoiceTokenResponse(BaseModel):
    token: str
    identity: str
    route: str
    agency: str


def _identity_secret() -> bytes:
    if not settings.twilio_auth_token:
        raise RuntimeError("TWILIO_AUTH_TOKEN is required for kiosk call signing.")
    return settings.twilio_auth_token.encode("utf-8")


def _encode_identity(to_number: str, agency: str, expires: int) -> str:
    payload = json.dumps(
        {"to": to_number, "agency": agency, "exp": expires},
        separators=(",", ":"),
    ).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    signature = hmac.new(
        _identity_secret(),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def _decode_identity(identity: str) -> dict | None:
    try:
        payload_b64, signature = identity.split(".", 1)
    except ValueError:
        return None

    expected = hmac.new(
        _identity_secret(),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None

    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(
            base64.urlsafe_b64decode((payload_b64 + padding).encode("ascii")).decode(
                "utf-8"
            )
        )
    except (ValueError, json.JSONDecodeError):
        return None

    expires = int(payload.get("exp") or 0)
    if expires < int(time.time()):
        return None
    return payload


def _prune_pending_calls(now: int | None = None) -> None:
    now = now or int(time.time())
    expired = [identity for identity, pending in _PENDING_CALLS.items() if int(pending.get("exp") or 0) < now]
    for identity in expired:
        _PENDING_CALLS.pop(identity, None)


def _store_pending_call(to_number: str, agency: str, device: KioskDevice) -> str:
    _prune_pending_calls()
    identity = str(uuid.uuid4())
    _PENDING_CALLS[identity] = {
        "to": to_number,
        "agency": agency,
        "device_code": device.device_code,
        "exp": int(time.time()) + _IDENTITY_TOKEN_TTL_SECONDS,
    }
    return identity


def _resolve_pending_call(identity: str) -> dict | None:
    _prune_pending_calls()
    pending = _PENDING_CALLS.pop(identity, None)
    if pending is not None:
        return pending
    # Backward compatibility for already-issued tokens from the older signed
    # identity flow. New tokens use short UUID identities because Twilio Client
    # identities are not a safe place to carry structured routing payloads.
    return _decode_identity(identity)


@router.post("/call/start", response_model=KioskCallResponse)
def kiosk_call_start(
    payload: KioskCallRequest,
    request: Request,
    device: KioskDevice = Depends(require_kiosk_device),
) -> KioskCallResponse:
    if request.headers.get("X-TalkBox-Mode") == "demo":
        logger.warning("kiosk call refused: device=%s reason=demo_mode", device.device_code)
        raise HTTPException(status_code=403, detail="Demo kiosks cannot place phone calls.")
    logger.info("kiosk call request: device=%s", device.device_code)
    result = kiosk_call_service.start_call(payload.phone)
    return KioskCallResponse(**result)


@router.post("/call/token", response_model=KioskVoiceTokenResponse)
def kiosk_call_token(
    payload: KioskVoiceTokenRequest,
    request: Request,
    device: KioskDevice = Depends(require_kiosk_device),
) -> KioskVoiceTokenResponse:
    if request.headers.get("X-TalkBox-Mode") == "demo":
        logger.warning("voice token refused: device=%s reason=demo_mode", device.device_code)
        raise HTTPException(status_code=403, detail="Demo kiosks cannot place phone calls.")
    now = time.monotonic()
    last_request = _LAST_TOKEN_REQUEST.get(device.device_code)
    if (
        last_request is not None
        and now - last_request < settings.kiosk_call_token_min_interval_seconds
    ):
        logger.warning("voice token refused: device=%s reason=rate_limited", device.device_code)
        raise HTTPException(status_code=429, detail="Please wait before starting another call.")

    if not _voice_service.browser_calling_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "Browser calling not configured. Set TWILIO_TWIML_APP_SID "
                "and TWILIO_PUBLIC_URL."
            ),
        )

    phone_raw = payload.phone.strip()
    digits = expand_short_code(normalize_digits(phone_raw))
    e164 = f"+{digits}" if phone_raw.startswith("+") else to_e164(digits)
    if not e164:
        raise HTTPException(status_code=400, detail="Invalid phone number.")

    agency = kiosk_call_service.find_allowlisted_agency(digits)
    if agency is None:
        logger.warning(
            "voice token refused: device=%s reason=destination_not_allowlisted",
            device.device_code,
        )
        raise HTTPException(status_code=403, detail="Number not on approved call list.")

    identity = _store_pending_call(e164, agency, device)
    route = _encode_identity(
        e164,
        agency,
        int(time.time()) + _IDENTITY_TOKEN_TTL_SECONDS,
    )
    token = _voice_service.generate_access_token(identity=identity)
    _LAST_TOKEN_REQUEST[device.device_code] = now
    logger.info(
        "voice token issued: device=%s identity=%s agency=%s",
        device.device_code,
        identity,
        agency,
    )
    return KioskVoiceTokenResponse(token=token, identity=identity, route=route, agency=agency)


def _twilio_webhook_url(path: str) -> str:
    public_url = settings.twilio_public_url.rstrip("/")
    if "/api/kiosk/call/" in public_url:
        return public_url.rsplit("/api/kiosk/call/", 1)[0] + path
    return urljoin(public_url + "/", path.lstrip("/"))


def _twilio_signature_valid(request: Request, form: dict, path: str) -> bool:
    if not settings.twilio_auth_token or not settings.twilio_public_url:
        logger.warning("Twilio webhook: missing signing configuration")
        return False

    signature = request.headers.get("X-Twilio-Signature", "")
    return RequestValidator(settings.twilio_auth_token).validate(
        _twilio_webhook_url(path), form, signature
    )


@router.post("/call/twiml")
async def kiosk_call_twiml(request: Request) -> Response:
    form = await request.form()

    if not _twilio_signature_valid(request, dict(form), "/api/kiosk/call/twiml"):
        logger.warning("twiml webhook: invalid Twilio signature — refusing")
        return Response(status_code=403)
    # Twilio normally posts the browser identity in the `From` form field as
    # `client:<identity>`. Keep the query-string fallback for local/manual
    # debugging where a developer may call the webhook URL directly.
    from_raw = str(form.get("From", "") or request.query_params.get("identity", ""))
    identity_key = from_raw.replace("client:", "").strip()
    route_key = str(form.get("route", "") or form.get("Route", "") or "").strip()
    pending = _decode_identity(route_key) if route_key else _resolve_pending_call(identity_key)
    if pending is None:
        logger.warning("twiml webhook: unknown/expired identity=%r", identity_key)
        vr = VoiceResponse()
        vr.say("This call could not be connected.")
        return Response(content=str(vr), media_type="application/xml")

    to_number = pending["to"]
    logger.info(
        "twiml webhook: device=%s connecting identity=%s",
        pending.get("device_code", "unknown"),
        identity_key,
    )
    twiml = _voice_service.build_dial_twiml(to_number)
    return Response(content=twiml, media_type="application/xml")


@router.post("/call/status")
async def kiosk_call_status(request: Request) -> dict:
    form = await request.form()
    if not _twilio_signature_valid(request, dict(form), "/api/kiosk/call/status"):
        logger.warning("status webhook: invalid Twilio signature — refusing")
        raise HTTPException(status_code=403, detail="Invalid Twilio signature.")
    sid = form.get("CallSid", "")
    status = form.get("CallStatus", "")
    duration = form.get("CallDuration", "")
    logger.info(
        "twilio status callback: sid=%s status=%s duration=%ss",
        sid,
        status,
        duration,
    )
    return {"received": True}
