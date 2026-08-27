"""Kiosk-facing HTTP routes (non-calling endpoints)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from src.application.services.kiosk_query_service import KioskQueryService
from src.application.services.kiosk_stt_service import KioskSttError, KioskSttService
from src.application.services.catalog_pull_service import catalog_pull_service
from src.infrastructure import catalog_sync
from src.infrastructure.config import settings
from src.presentation.query_runtime import get_query_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kiosk", tags=["kiosk"])

kiosk_query_service = KioskQueryService(get_query_handler)
kiosk_stt_service = KioskSttService()


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
    search_mode: str = "none"
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
    resource_search_mode: str
    idle_reset_seconds: int
    calling_enabled: bool
    speech_enabled: bool
    speech_max_seconds: int
    call_idle_warn_seconds: int
    screen_dim_seconds: int
    menu: list[KioskMenuItem]


class KioskEventRequest(BaseModel):
    session_id: str | None = None
    event_type: str
    payload: dict | None = None


class KioskSpeechResponse(BaseModel):
    text: str
    provider: str
    duration_ms: int
    fallback_used: bool = False
    error: str | None = None


_HOME_MENU: list[dict] = [
    {
        "key": 1,
        "action": "QUICK_QUERY",
        "label": "Shelter",
        "query": "I need shelter tonight",
    },
    {"key": 2, "action": "QUICK_QUERY", "label": "Food", "query": "I need food"},
    {
        "key": 3,
        "action": "QUICK_QUERY",
        "label": "Medical care",
        "query": "I need a doctor or clinic",
    },
    {
        "key": 4,
        "action": "QUICK_QUERY",
        "label": "Mental health",
        "query": "I need mental health help",
    },
    {
        "key": 5,
        "action": "QUICK_QUERY",
        "label": "Transportation",
        "query": "I need a ride",
    },
    {
        "key": 6,
        "action": "QUICK_QUERY",
        "label": "Veterans",
        "query": "I am a veteran and need help",
    },
    {
        "key": 7,
        "action": "QUICK_QUERY",
        "label": "Youth services",
        "query": "I am a young person and need help",
    },
    {"key": 8, "action": "VOICE_INPUT", "label": "Speak / type a need", "query": None},
    {"key": 9, "action": "CALL_211", "label": "Call 211 help line", "query": None},
]


@router.get("/config", response_model=KioskConfigResponse)
def kiosk_config() -> KioskConfigResponse:
    return KioskConfigResponse(
        name="Talk Box",
        mock_mode=settings.kiosk_mock_query,
        resource_search_mode=settings.resource_search_mode,
        idle_reset_seconds=settings.kiosk_idle_reset_seconds,
        calling_enabled=settings.kiosk_calling_enabled,
        speech_enabled=settings.kiosk_stt_enabled,
        speech_max_seconds=settings.kiosk_stt_max_seconds,
        call_idle_warn_seconds=settings.kiosk_call_idle_warn_seconds,
        screen_dim_seconds=settings.kiosk_screen_dim_seconds,
        menu=[KioskMenuItem(**m) for m in _HOME_MENU],
    )


@router.post("/query", response_model=KioskQueryResponse)
async def kiosk_query(payload: KioskQueryRequest) -> KioskQueryResponse:
    logger.info("kiosk query: %r", payload.query)
    result = kiosk_query_service.query(payload.query)
    logger.info(
        "kiosk query result: category=%s items=%d empty=%s search_mode=%s",
        result.get("category"),
        len(result.get("items") or []),
        result.get("empty"),
        result.get("search_mode"),
    )
    return KioskQueryResponse(**result)


@router.get("/directory", response_model=KioskQueryResponse)
async def kiosk_directory() -> KioskQueryResponse:
    """Flat A–Z organization directory for the Browse tab."""
    result = kiosk_query_service.directory()
    logger.info(
        "kiosk directory: items=%d empty=%s search_mode=%s",
        len(result.get("items") or []),
        result.get("empty"),
        result.get("search_mode"),
    )
    return KioskQueryResponse(**result)


@router.post("/speech/transcribe", response_model=KioskSpeechResponse)
async def kiosk_speech_transcribe(audio: UploadFile = File(...)) -> KioskSpeechResponse:
    uploaded = await audio.read(settings.kiosk_stt_max_upload_bytes + 1)
    if len(uploaded) > settings.kiosk_stt_max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded audio is too large.")
    logger.info(
        "kiosk speech upload: filename=%s bytes=%d",
        audio.filename,
        len(uploaded),
    )
    try:
        result = kiosk_stt_service.transcribe(uploaded, audio.filename or "audio.webm")
    except KioskSttError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    logger.info(
        "kiosk speech transcribed: provider=%s fallback=%s chars=%d duration_ms=%d",
        result.provider,
        result.fallback_used,
        len(result.text),
        result.duration_ms,
    )
    return KioskSpeechResponse(**result.as_dict())


@router.post("/events", status_code=202)
def kiosk_events(event: KioskEventRequest) -> dict:
    logger.info(
        "kiosk event: type=%s session=%s payload=%s",
        event.event_type,
        event.session_id,
        event.payload,
    )
    return {"accepted": True}


@router.get("/catalog/version")
def catalog_version() -> dict:
    return catalog_sync.load_version()


@router.get("/catalog")
def catalog_snapshot() -> dict:
    return catalog_sync.load_snapshot()


@router.get("/catalog/status")
def catalog_pull_status() -> dict:
    local = catalog_sync.load_version()
    return {**catalog_pull_service.status(), **local}


@router.post("/catalog/pull")
async def catalog_pull(force: bool = False) -> dict:
    if not catalog_pull_service.configured:
        raise HTTPException(
            status_code=400,
            detail="This node has no TALKBOX_CENTRAL_API_BASE_URL; nothing to pull.",
        )
    try:
        return await catalog_pull_service.pull_if_needed(force=force)
    except Exception as exc:
        logger.exception("manual catalog pull failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

