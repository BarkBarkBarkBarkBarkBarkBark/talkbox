"""Allowlisted outbound calling for the kiosk.

Safety model (roadmap principle: ``no_arbitrary_dialing``):

  1. The kiosk can only request a call by phone number.
  2. The backend normalizes the number and checks it against the agencies
     database — the database IS the allowlist. A number that does not belong
     to a seeded agency is refused (the optional ``KIOSK_TEST_CALL_NUMBER``
     env var adds one extra number for end-to-end testing).
  3. Only then is the Twilio Voice REST API invoked.

Every attempt — allowed or refused — is logged so the rolling log shows
exactly what the kiosk tried to dial.
"""

from __future__ import annotations

import logging
import re

from src.infrastructure.config import settings
from src.infrastructure.database import get_db_connection
from src.infrastructure.voice.twilio_voice_service import TwilioVoiceService

logger = logging.getLogger(__name__)


def normalize_digits(raw: str | None) -> str:
    return re.sub(r"\D", "", str(raw or ""))


def to_e164(digits: str) -> str | None:
    """US-centric normalization to +E.164."""
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None


class KioskCallService:
    def __init__(self, voice_service: TwilioVoiceService):
        self._voice = voice_service

    @property
    def calling_enabled(self) -> bool:
        return settings.kiosk_calling_enabled and self._voice.configured

    # ─── Allowlist ───────────────────────────────────────────────────────
    def find_allowlisted_agency(self, digits: str) -> str | None:
        """Return the agency name whose phone matches, or None.

        Matches on the last 10 digits so '9164476243', '19164476243' and
        formatted variants in the CSV all line up.
        """
        if len(digits) < 10:
            return None
        last10 = digits[-10:]

        test_number = normalize_digits(settings.kiosk_test_call_number)
        if test_number and test_number[-10:] == last10:
            return "Test number (KIOSK_TEST_CALL_NUMBER)"

        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT agency_name
                FROM agencies
                WHERE RIGHT(regexp_replace(COALESCE(phone_number, ''), '\\D', '', 'g'), 10) = %s
                LIMIT 1;
                """,
                (last10,),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    # ─── Calling ─────────────────────────────────────────────────────────
    def start_call(self, raw_phone: str) -> dict:
        digits = normalize_digits(raw_phone)
        e164 = to_e164(digits)

        if not e164:
            logger.warning("kiosk call refused (bad number): %r", raw_phone)
            return {"allowed": False, "status": "refused", "reason": "invalid_number"}

        agency = self.find_allowlisted_agency(digits)
        if agency is None:
            logger.warning("kiosk call refused (not allowlisted): %s", e164)
            return {"allowed": False, "status": "refused", "reason": "not_allowlisted"}

        if not self.calling_enabled:
            logger.info("kiosk call simulated (calling disabled): %s -> %s", e164, agency)
            return {"allowed": True, "status": "simulated", "agency": agency}

        announce = (
            f"Hello. This is the Pointer community resource line, "
            f"calling {agency}. This is a connection test. Goodbye."
        )
        try:
            sid = self._voice.place_call(e164, announce)
        except Exception as exc:
            logger.exception("kiosk call failed: %s -> %s", e164, agency)
            return {"allowed": True, "status": "failed", "agency": agency, "reason": str(exc)}

        logger.info("kiosk call placed: %s -> %s (sid=%s)", e164, agency, sid)
        return {"allowed": True, "status": "initiated", "agency": agency, "sid": sid}
