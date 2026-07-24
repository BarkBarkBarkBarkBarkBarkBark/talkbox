"""Resource synchronization health and kiosk snapshot endpoints."""

from fastapi import APIRouter, HTTPException, Query

from src.application.services.resource_sync_service import resource_sync_service

router = APIRouter(tags=["resources"])


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
def readyz() -> dict:
    return {"status": "ready", "resource_cache_available": resource_sync_service.snapshot is not None}


@router.get("/api/kiosk/resources")
async def kiosk_resources(kiosk_code: str | None = Query(default=None)) -> dict:
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


@router.get("/api/kiosk/sync-status")
def kiosk_sync_status() -> dict:
    return resource_sync_service.status()