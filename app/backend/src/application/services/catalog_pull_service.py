"""Kiosk-side poller: watch Fly catalog version and replace local Postgres."""

from __future__ import annotations

import asyncio
import logging

import httpx

from src.infrastructure import catalog_sync
from src.infrastructure.config import settings

logger = logging.getLogger(__name__)


class CatalogPullService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self.last_error: str | None = None
        self.last_applied_version: int | None = None
        self.last_pull_at: str | None = None

    @property
    def configured(self) -> bool:
        return bool(settings.talkbox_central_api_base_url)

    def status(self) -> dict:
        return {
            "configured": self.configured,
            "central": settings.talkbox_central_api_base_url or None,
            "last_applied_version": self.last_applied_version,
            "last_pull_at": self.last_pull_at,
            "last_error": self.last_error,
        }

    async def start(self) -> None:
        if not self.configured:
            logger.info("catalog pull disabled (no TALKBOX_CENTRAL_API_BASE_URL)")
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "catalog pull started central=%s interval=%ss",
            settings.talkbox_central_api_base_url,
            settings.talkbox_catalog_pull_interval_seconds,
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await self.pull_if_needed()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("catalog pull failed")
            await asyncio.sleep(settings.talkbox_catalog_pull_interval_seconds)

    async def pull_if_needed(self, *, force: bool = False) -> dict:
        if not self.configured:
            raise RuntimeError("TALKBOX_CENTRAL_API_BASE_URL is not set")
        remote = await self._get_json("/api/kiosk/catalog/version")
        remote_version = int(remote["content_version"])
        local = catalog_sync.load_version()
        local_version = int(local["content_version"])
        if not force and remote_version <= local_version:
            self.last_error = None
            self.last_applied_version = local_version
            return {
                "pulled": False,
                "content_version": local_version,
                "remote_version": remote_version,
            }
        snapshot = await self._get_json("/api/kiosk/catalog")
        result = await asyncio.to_thread(catalog_sync.replace_local_catalog, snapshot)
        self.last_applied_version = result["content_version"]
        self.last_pull_at = result.get("pushed_at") or snapshot.get("updated_at")
        self.last_error = None
        logger.info(
            "catalog pulled version=%s agencies=%s visible=%s",
            result["content_version"],
            result["agency_count"],
            result["visible_count"],
        )
        return {"pulled": True, **result, "remote_version": remote_version}

    async def _get_json(self, path: str) -> dict:
        headers = {"Accept": "application/json"}
        key = settings.talkbox_client_snapshot_key
        if key:
            headers["Authorization"] = f"Bearer {key}"
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(
            base_url=settings.talkbox_central_api_base_url.rstrip("/"),
            headers=headers,
            timeout=timeout,
        ) as client:
            response = await client.get(path)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Catalog response must be an object")
        return payload


catalog_pull_service = CatalogPullService()
