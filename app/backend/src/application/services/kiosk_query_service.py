"""Kiosk-facing wrapper around the existing :class:`QueryHandler`.

Transforms the rich web query response into a compact, numbered, display-safe
payload optimized for a 6-inch keypad screen. Long descriptions are truncated
and at most :data:`MAX_ITEMS` resources are returned so each maps to a single
number key (1-9).

When ``settings.kiosk_mock_query`` is true (or the real pipeline raises), a
curated set of sample resources is returned instead. This lets the kiosk demo
run on a laptop or Raspberry Pi with no OpenAI key and no seeded database.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from src.application.services.query_handler import QueryHandler
from src.infrastructure.config import settings

logger = logging.getLogger(__name__)

MAX_ITEMS = 9
MAX_DESCRIPTION_CHARS = 140

# 211 is the always-available human fallback for social services.
RESOURCE_211 = {
    "name": "211 Sacramento — Community Resource Line",
    "phone": "+19164981000",
    "address": None,
    "description": "Free, confidential help finding shelter, food, and local services. Available 24/7.",
    "category": "Help line",
}

# ─── Mock catalog ────────────────────────────────────────────────────────────
# Keyword → (category label, list of real resources). Used only in mock mode.
# Generated from the original Health Scout DBs by scripts/build_agencies_csv.py
# so offline demos show real Sacramento agencies, not invented samples.
_MOCK_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "infrastructure" / "seeds" / "kiosk_mock_catalog.json"
)


def _load_mock_catalog() -> dict[str, dict]:
    try:
        return json.loads(_MOCK_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.exception("could not load kiosk mock catalog from %s", _MOCK_CATALOG_PATH)
        return {}


_MOCK_CATALOG: dict[str, dict] = _load_mock_catalog()

# Phrase fragments that route a free-text query to a mock category.
_MOCK_KEYWORDS: list[tuple[str, str]] = [
    (r"shelter|sleep|bed|housing|homeless|night", "shelter"),
    (r"food|eat|hungry|meal|grocer|pantry", "food"),
    (r"mental|counsel|therapy|crisis|depress|anxiet|suicid", "mental_health"),
    (r"doctor|medical|clinic|health|dentist|sick|nurse", "medical"),
    (r"transport|ride|bus|paratransit|appointment", "transport"),
    (r"veteran|military|vet\b", "veterans"),
    (r"youth|teen|young|kid", "youth"),
]


def _truncate(text: str | None) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    if len(text) <= MAX_DESCRIPTION_CHARS:
        return text
    return text[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"


def _format_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 11 and digits.startswith("1"):
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"
    return raw


class KioskQueryService:
    """Adapts :class:`QueryHandler` output for keypad-first kiosk screens."""

    def __init__(self, query_handler: QueryHandler):
        self._handler = query_handler

    def query(self, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            return self._empty_payload()

        if settings.kiosk_mock_query:
            return self._mock_query(text)

        try:
            result = self._run_structured_query(text)
        except Exception:
            logger.exception("kiosk query failed; falling back to mock catalog")
            return self._mock_query(text)

        return self._normalize(result)

    def _run_structured_query(self, text: str) -> dict:
        """Deterministic kiosk pipeline: embedding similarity routes to a
        category, then a plain SQL lookup returns structured rows.

        Unlike the web ``handle_query`` path, the ``Healthscout`` category is
        NOT sent through the LLM insurance/specialty extractor — kiosk users
        are often in crisis, so the kiosk intentionally avoids any LLM
        interpretation and serves the deterministic Medical Clinic listing
        instead.
        """
        category = self._handler.categorizer.retrieve_category(text)
        if category == "Healthscout":
            category = "Medical Clinic"
        return self._handler.executor.execute_query(category)

    # ─── Real pipeline ───────────────────────────────────────────────────
    def _normalize(self, result: dict) -> dict:
        payload = result.get("results")
        if not payload:
            return self._empty_payload(result.get("response"))

        category = payload.get("category")
        raw_items: list[dict]
        if payload.get("type") == "doctors":
            raw_items = [self._doctor_to_item(d) for d in payload.get("items_doctors", [])]
        else:
            raw_items = [self._agency_to_item(a) for a in payload.get("items_agencies", [])]

        items = self._number_items(raw_items)
        if not items:
            return self._empty_payload(result.get("response"))
        return self._payload(category, items)

    @staticmethod
    def _agency_to_item(a: dict) -> dict:
        return {
            "name": a.get("name") or "Resource",
            "phone": a.get("phone"),
            "address": a.get("address"),
            "description": a.get("description"),
        }

    @staticmethod
    def _doctor_to_item(d: dict) -> dict:
        full = " ".join(p for p in [d.get("first_name"), d.get("last_name")] if p).strip()
        name = f"Dr. {full}" if full else "Provider"
        return {
            "name": name,
            "phone": d.get("phone"),
            "address": d.get("address"),
            "description": d.get("specialty"),
        }

    # ─── Mock pipeline ───────────────────────────────────────────────────
    def _mock_query(self, text: str) -> dict:
        key = self._match_keyword(text)
        entry = _MOCK_CATALOG.get(key) if key else None
        if not entry:
            return self._empty_payload()
        items = self._number_items([dict(i) for i in entry["items"]])
        return self._payload(entry["category"], items)

    @staticmethod
    def _match_keyword(text: str) -> str | None:
        low = text.lower()
        for pattern, key in _MOCK_KEYWORDS:
            if re.search(pattern, low):
                return key
        return None

    # ─── Shared shaping ──────────────────────────────────────────────────
    @staticmethod
    def _number_items(raw_items: list[dict]) -> list[dict]:
        items: list[dict] = []
        for idx, it in enumerate(raw_items[:MAX_ITEMS], start=1):
            phone = it.get("phone")
            items.append(
                {
                    "number": idx,
                    "name": it.get("name") or "Resource",
                    "phone": re.sub(r"\D", "", str(phone)) if phone else None,
                    "phone_display": _format_phone(phone),
                    "address": it.get("address"),
                    "description": _truncate(it.get("description")),
                    # Calling is gated by a backend allowlist (added in M6). Until
                    # then nothing is callable for real; the demo simulates it.
                    "callable": False,
                }
            )
        return items

    def _payload(self, category: str | None, items: list[dict]) -> dict:
        names = ", ".join(i["name"] for i in items[:3])
        summary = (
            f"Found {len(items)} {category or 'resource'} option"
            f"{'s' if len(items) != 1 else ''}. {names}."
        )
        return {
            "category": category,
            "items": items,
            "empty": False,
            "spoken_summary": summary,
            "fallback": self._fallback_item(),
        }

    def _empty_payload(self, message: str | None = None) -> dict:
        return {
            "category": None,
            "items": [],
            "empty": True,
            "spoken_summary": (
                "I could not find a match. You can call 211 for help finding "
                "shelter, food, or other services."
            ),
            "message": message,
            "fallback": self._fallback_item(),
        }

    @staticmethod
    def _fallback_item() -> dict:
        return {
            "number": 0,
            "name": RESOURCE_211["name"],
            "phone": re.sub(r"\D", "", RESOURCE_211["phone"]),
            "phone_display": _format_phone(RESOURCE_211["phone"]),
            "address": RESOURCE_211["address"],
            "description": _truncate(RESOURCE_211["description"]),
            "callable": False,
        }
