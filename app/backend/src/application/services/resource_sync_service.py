"""Atomic, last-known-good synchronization of public TalkBox resources."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from src.infrastructure.config import settings
from src.infrastructure.fsc_resource_client import (
    BootstrapSnapshot,
    FSCResourceAuthError,
    FSCResourceClient,
)
from src.infrastructure.resource_snapshot_cache import ResourceSnapshotCache
from src.infrastructure.talkbox_snapshot_client import ClientSnapshotClient

logger = logging.getLogger(__name__)


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")[-10:]


class ResourceSyncService:
    def __init__(self, cache_path: str | Path | None = None) -> None:
        self._snapshot: BootstrapSnapshot | None = None
        self._cache = ResourceSnapshotCache(cache_path) if cache_path else None
        self._client: FSCResourceClient | None = None
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self.last_sync_attempt: datetime | None = None
        self.last_successful_sync: datetime | None = None
        self.last_error_type: str | None = None

    @property
    def configured(self) -> bool:
        return self.upstream_source != "none"

    @property
    def upstream_source(self) -> str:
        if settings.fsc_resource_api_base_url and settings.fsc_resource_api_key:
            return "fsc-api"
        if settings.talkbox_central_api_base_url and settings.talkbox_client_snapshot_key:
            return "talkbox-central"
        return "none"

    @property
    def snapshot(self) -> BootstrapSnapshot | None:
        return self._snapshot

    @property
    def stale(self) -> bool:
        if self.last_successful_sync is None:
            return True
        age = (datetime.now(UTC) - self.last_successful_sync).total_seconds()
        return age > settings.fsc_resource_cache_max_age_seconds

    async def start(self) -> None:
        await self.restore_cached_snapshot()
        if not settings.fsc_resource_sync_enabled or not self.configured:
            return
        if self.upstream_source == "fsc-api":
            self._client = FSCResourceClient(
                settings.fsc_resource_api_base_url,
                settings.fsc_resource_api_key,
                settings.fsc_resource_request_timeout_seconds,
            )
        else:
            self._client = ClientSnapshotClient(
                settings.talkbox_central_api_base_url,
                settings.talkbox_client_snapshot_key,
                settings.fsc_resource_request_timeout_seconds,
            )
        await self.refresh()
        self._task = asyncio.create_task(self._periodic_sync())

    async def restore_cached_snapshot(self) -> bool:
        if self._cache is None:
            return False
        try:
            cached = await asyncio.to_thread(self._cache.load)
            if cached is None:
                return False
            snapshot, fetched_at = cached
            if not snapshot.services:
                raise ValueError("Cached bootstrap contains no published TalkBox services")
            self._snapshot = snapshot
            self.last_successful_sync = fetched_at
            logger.info(
                "resource_cache_restored content_version=%s resource_count=%d",
                snapshot.content_version,
                len(snapshot.services),
            )
            return True
        except Exception as exc:
            self.last_error_type = type(exc).__name__
            try:
                quarantine_path = await asyncio.to_thread(self._cache.quarantine)
            except OSError:
                quarantine_path = None
            if quarantine_path is not None:
                logger.warning("resource_cache_quarantined path=%s", quarantine_path)
            logger.warning("resource_cache_restore_failed error_class=%s", type(exc).__name__)
            return False

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client is not None:
            await self._client.close()

    async def ensure_available(self) -> BootstrapSnapshot | None:
        if self._snapshot is None and self._client is not None:
            await self.refresh()
        elif self.stale and self._client is not None and not self._lock.locked():
            asyncio.create_task(self.refresh())
        return self._snapshot

    async def refresh(self) -> bool:
        if self._client is None:
            return False
        async with self._lock:
            self.last_sync_attempt = datetime.now(UTC)
            try:
                version = await self._client.get_version()
                if self._snapshot and self._snapshot.content_version == version.content_version:
                    self.last_error_type = None
                    logger.info("resource_sync_unchanged content_version=%s", version.content_version)
                    return False
                candidate = await self._client.get_bootstrap()
                if candidate.content_version != version.content_version:
                    raise ValueError("Bootstrap content version does not match version endpoint")
                if not candidate.services:
                    raise ValueError("Bootstrap contains no published TalkBox services")
                fetched_at = datetime.now(UTC)
                if self._cache is not None:
                    await asyncio.to_thread(self._cache.save, candidate, fetched_at)
                self._snapshot = candidate
                self.last_successful_sync = fetched_at
                self.last_error_type = None
                logger.info(
                    "resource_sync_updated content_version=%s resource_count=%d",
                    candidate.content_version,
                    len(candidate.services),
                )
                return True
            except Exception as exc:
                self.last_error_type = type(exc).__name__
                event = "upstream_auth_failed" if isinstance(exc, FSCResourceAuthError) else "resource_sync_failed"
                logger.warning("%s error_class=%s", event, type(exc).__name__)
                return False

    def approved_agency(self, phone: str) -> str | None:
        target = _digits(phone)
        if not target or self._snapshot is None:
            return None
        for service in self._snapshot.services:
            if _digits(service.approved_phone()) == target:
                return service.name
        return None

    def directory(self) -> list[dict]:
        """All talkbox-visible services sorted by name (A–Z) for kiosk Browse."""
        if self._snapshot is None:
            return []
        services = [
            service
            for service in self._snapshot.services
            if service.talkbox_visible
            and (
                not service.status
                or service.status.lower() in {"active", "published", "approved"}
            )
        ]
        services.sort(key=lambda s: (s.name or "").lower())
        items: list[dict] = []
        for service in services:
            approved_phone = service.approved_phone()
            address = ", ".join(
                part
                for part in (service.address, service.city, service.state, service.postal_code)
                if part
            ) or None
            items.append(
                {
                    "name": service.name,
                    "phone": approved_phone,
                    "address": address,
                    "description": service.description,
                    "callable": bool(approved_phone),
                }
            )
        return items

    def query(self, text: str, limit: int = 9) -> tuple[str | None, list[dict]]:
        if self._snapshot is None:
            return None, []
        tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
        ranked: list[tuple[int, object]] = []
        for service in self._snapshot.services:
            if not service.talkbox_visible or (service.status and service.status not in {"active", "published", "approved"}):
                continue
            searchable = " ".join(
                part for part in (service.name, service.category, service.description) if part
            ).lower()
            score = sum(1 for token in tokens if token in searchable)
            if score:
                ranked.append((score, service))
        ranked.sort(key=lambda item: (-item[0], item[1].name.lower()))
        services = [item[1] for item in ranked[:limit]]
        items = []
        for service in services:
            approved_phone = service.approved_phone()
            address = ", ".join(
                part for part in (service.address, service.city, service.state, service.postal_code) if part
            ) or None
            items.append(
                {
                    "name": service.name,
                    "phone": approved_phone,
                    "address": address,
                    "description": service.description,
                    "callable": bool(approved_phone),
                }
            )
        category = services[0].category if services else None
        return category, items

    def query_by_resource_ids(
        self, resource_ids: list[str], limit: int = 9
    ) -> tuple[str | None, list[dict]]:
        if self._snapshot is None:
            return None, []
        services_by_id = {
            str(service.id): service
            for service in self._snapshot.services
            if service.talkbox_visible
            and (
                not service.status
                or service.status.lower() in {"active", "published", "approved"}
            )
        }
        services = [
            services_by_id[resource_id]
            for resource_id in resource_ids[:limit]
            if resource_id in services_by_id
        ]
        items = []
        for service in services:
            approved_phone = service.approved_phone()
            address = ", ".join(
                part
                for part in (
                    service.address,
                    service.city,
                    service.state,
                    service.postal_code,
                )
                if part
            ) or None
            items.append(
                {
                    "name": service.name,
                    "phone": approved_phone,
                    "address": address,
                    "description": service.description,
                    "callable": bool(approved_phone),
                }
            )
        category = services[0].category if services else None
        return category, items

    async def _periodic_sync(self) -> None:
        while True:
            await asyncio.sleep(settings.fsc_resource_sync_interval_seconds)
            await self.refresh()

    def status(self) -> dict:
        return {
            "sync_enabled": settings.fsc_resource_sync_enabled,
            "upstream_configured": self.configured,
            "upstream_source": self.upstream_source,
            "last_successful_sync": self.last_successful_sync,
            "last_sync_attempt": self.last_sync_attempt,
            "content_version": self._snapshot.content_version if self._snapshot else None,
            "cache_available": self._snapshot is not None,
            "stale": self.stale,
            "last_error_type": self.last_error_type,
        }


resource_sync_service = ResourceSyncService(cache_path=settings.fsc_resource_cache_path)