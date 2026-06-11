"""Twilio Voice service — REST calls + Browser SDK token/TwiML support.

Two calling modes:
  1. Legacy REST (place_call): backend dials out and speaks a TTS message.
     Kept for fallback / non-SDK environments.
  2. Browser SDK (generate_access_token + build_dial_twiml): the kiosk
     browser connects to Twilio as a soft-phone; Twilio bridges the call
     to the recipient's real phone number.

Safety: this service never decides who may be called. All allowlist checks
live in KioskCallService before any method here is invoked.
"""

from __future__ import annotations

import logging
import uuid
from xml.sax.saxutils import escape

from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.rest import Client
from twilio.twiml.voice_response import Dial, VoiceResponse

from src.infrastructure.config import settings

logger = logging.getLogger(__name__)


class TwilioVoiceService:
    def __init__(self):
        self._client: Client | None = None

    @property
    def configured(self) -> bool:
        return bool(
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and settings.twilio_phone_number
        )

    @property
    def browser_calling_configured(self) -> bool:
        """True when TwiML App SID, public URL, and a signing API Key are set.

        A real API Key (SK…) + secret is mandatory: Twilio rejects Voice
        access tokens signed with the account SID/auth token.
        """
        return self.configured and bool(
            settings.twilio_twiml_app_sid
            and settings.twilio_public_url
            and settings.twilio_api_key_sid
            and settings.twilio_api_key_secret
        )

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        return self._client

    # ─── Legacy REST call (TTS announcement) ─────────────────────────────
    def place_call(self, to_number: str, announce: str) -> str:
        """Place an outbound call that speaks ``announce``. Returns the call SID."""
        twiml = f"<Response><Say voice='alice'>{escape(announce)}</Say></Response>"
        call = self._get_client().calls.create(
            twiml=twiml,
            to=to_number,
            from_=settings.twilio_phone_number,
        )
        logger.info("twilio call created: sid=%s to=%s", call.sid, to_number)
        return call.sid

    # ─── Browser SDK: access token ───────────────────────────────────────
    def generate_access_token(self, identity: str | None = None) -> str:
        """Return a short-lived Twilio Voice access token for the browser SDK.

        ``identity`` is a per-session UUID used to route the TwiML webhook
        back to the correct pending call.  A new UUID is generated if not
        provided.
        """
        if not identity:
            identity = str(uuid.uuid4())

        token = AccessToken(
            settings.twilio_account_sid,
            # Twilio requires a real API Key (SK…) + secret as the signing
            # key — account SID/auth token are rejected (error 20101).
            settings.twilio_api_key_sid,
            settings.twilio_api_key_secret,
            identity=identity,
            ttl=90,  # seconds — short-lived; enough for confirm + connect
        )
        grant = VoiceGrant(
            outgoing_application_sid=settings.twilio_twiml_app_sid,
            incoming_allow=False,  # kiosk is outbound-only
        )
        token.add_grant(grant)
        logger.debug("access token issued: identity=%s", identity)
        return token.to_jwt()

    # ─── Browser SDK: TwiML webhook ──────────────────────────────────────
    def build_dial_twiml(self, to_number: str) -> str:
        """Return TwiML that dials ``to_number``.

        Twilio POSTs to /api/kiosk/call/twiml when the browser SDK connects;
        the backend looks up the pending call by identity and calls this.
        """
        response = VoiceResponse()
        dial = Dial(
            caller_id=settings.twilio_phone_number,
            answer_on_bridge=True,  # ring tone on browser end until answered
        )
        dial.number(to_number)
        response.append(dial)
        twiml = str(response)
        logger.debug("twiml built for %s: %s", to_number, twiml)
        return twiml
