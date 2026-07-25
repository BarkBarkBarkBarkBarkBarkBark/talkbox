"""Resource synchronization health and kiosk snapshot endpoints."""

import hmac

from fastapi import APIRouter, Header, HTTPException, Query

from src.application.services.resource_sync_service import resource_sync_service
from src.infrastructure.config import settings

router = APIRouter(tags=["resources"])


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
def readyz() -> dict:
    return {"status": "ready", "resource_cache_available": resource_sync_service.snapshot is not None}


@router.get("/api/kiosk/resources")
async def kiosk_resources(
    kiosk_code: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    _authorize_snapshot(authorization)
    snapshot = await resource_sync_service.ensure_available()
    if snapshot is None:
        raise HTTPException(status_code=503, detail="Resource snapshot is not available")
    payload = snapshot.model_dump(mode="json")
    payload.update(
        {
            "fetched_at": resource_sync_service.last_successful_sync,
            "upstream_generated_at": snapshot.generated_at,
            "stale": resource_sync_service.stale,
        }
    )
    return payload


@router.get("/api/kiosk/resource-version")
async def kiosk_resource_version(
    authorization: str | None = Header(default=None),
) -> dict:
    _authorize_snapshot(authorization)
    snapshot = await resource_sync_service.ensure_available()
    if snapshot is None:
        raise HTTPException(status_code=503, detail="Resource snapshot is not available")
    return {
        "content_version": snapshot.content_version,
        "generated_at": snapshot.generated_at,
    }


@router.get("/api/kiosk/sync-status")
def kiosk_sync_status() -> dict:
    return resource_sync_service.status()


def _authorize_snapshot(authorization: str | None) -> None:
    accepted = {
        key.strip()
        for key in settings.talkbox_snapshot_publish_keys.split(",")
        if key.strip()
    }
    if not accepted:
        return
    scheme, _, credential = (authorization or "").partition(" ")
    authorized = scheme.lower() == "bearer" and any(
        hmac.compare_digest(credential, expected) for expected in accepted
    )
    if not authorized:
        raise HTTPException(status_code=401, detail="Snapshot authentication failed")