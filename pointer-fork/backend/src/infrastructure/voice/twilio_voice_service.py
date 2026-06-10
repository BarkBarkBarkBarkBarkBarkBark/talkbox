"""Thin wrapper around the Twilio Voice REST API.

Follows the server-side pattern recommended in the Twilio docs
(https://www.twilio.com/docs/voice/tutorials/how-to-make-outbound-phone-calls):
``client.calls.create(twiml=..., to=..., from_=...)``.

This service NEVER decides who may be called — callers must run the number
through the allowlist (see ``KioskCallService``) first. Browser-as-speakerphone
calling (Voice JS SDK + access tokens + public TwiML webhook) is the follow-up
milestone; this REST path is what lets us validate credentials and place
allowlisted calls today.
"""

from __future__ import annotations

import logging
from xml.sax.saxutils import escape

from twilio.rest import Client

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

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        return self._client

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
