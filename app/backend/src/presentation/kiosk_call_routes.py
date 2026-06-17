"""Kiosk Twilio calling routes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, HTTPException, Request, Response
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kiosk", tags=["kiosk"])

_voice_service = TwilioVoiceService()
kiosk_call_service = KioskCallService(_voice_service)

_PENDING_TTL = 90


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


@router.post("/call/start", response_model=KioskCallResponse)
def kiosk_call_start(payload: KioskCallRequest) -> KioskCallResponse:
    logger.info("kiosk call request: phone=%r name=%r", payload.phone, payload.name)
    result = kiosk_call_service.start_call(payload.phone)
    return KioskCallResponse(**result)


@router.post("/call/token", response_model=KioskVoiceTokenResponse)
def kiosk_call_token(payload: KioskVoiceTokenRequest) -> KioskVoiceTokenResponse:
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
        raise HTTPException(status_code=403, detail="Number not on approved call list.")

    identity = _encode_identity(e164, agency, int(time.time()) + _PENDING_TTL)
    token = _voice_service.generate_access_token(identity=identity)
    logger.info(
        "voice token issued: identity=%s agency=%s to=%s",
        identity,
        agency,
        e164,
    )
    return KioskVoiceTokenResponse(token=token, identity=identity, agency=agency)


def _twilio_signature_valid(request: Request, form: dict) -> bool:
    if not settings.twilio_auth_token or not settings.twilio_public_url:
        logger.warning("twiml webhook: missing Twilio signing configuration")
        return False

    public_url = settings.twilio_public_url.rstrip("/")
    url = (
        public_url
        if public_url.endswith("/api/kiosk/call/twiml")
        else public_url + "/api/kiosk/call/twiml"
    )
    signature = request.headers.get("X-Twilio-Signature", "")
    return RequestValidator(settings.twilio_auth_token).validate(url, form, signature)


@router.post("/call/twiml")
async def kiosk_call_twiml(request: Request) -> Response:
    form = await request.form()

    if not _twilio_signature_valid(request, dict(form)):
        logger.warning("twiml webhook: invalid Twilio signature — refusing")
        return Response(status_code=403)
    from_raw = str(form.get("From", "") or request.query_params.get("identity", ""))
    identity_key = from_raw.replace("client:", "").strip()
    pending = _decode_identity(identity_key)
    if pending is None:
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
    form = await request.form()
    sid = form.get("CallSid", "")
    status = form.get("CallStatus", "")
    to = form.get("To", "")
    duration = form.get("CallDuration", "")
    logger.info(
        "twilio status callback: sid=%s status=%s to=%s duration=%ss",
        sid,
        status,
        to,
        duration,
    )
    return {"received": True}
