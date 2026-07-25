"""Client for a TalkBox appliance to download public snapshots from Fly."""

from __future__ import annotations

import httpx

from src.infrastructure.fsc_resource_client import (
    BootstrapSnapshot,
    ContentVersion,
    FSCResourceAuthError,
    FSCResourceError,
)


class ClientSnapshotClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 10.0):
        timeout = httpx.Timeout(timeout_seconds, connect=timeout_seconds)
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_version(self) -> ContentVersion:
        return ContentVersion.model_validate(
            await self._get_json("/api/kiosk/resource-version")
        )

    async def get_bootstrap(self) -> BootstrapSnapshot:
        return BootstrapSnapshot.model_validate(
            await self._get_json("/api/kiosk/resources")
        )

    async def _get_json(self, path: str) -> dict:
        try:
            response = await self._client.get(path)
            if response.status_code in {401, 403}:
                raise FSCResourceAuthError("TalkBox snapshot authentication failed")
            response.raise_for_status()
            payload = response.json()
        except FSCResourceError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise FSCResourceError(type(exc).__name__) from exc
        if not isinstance(payload, dict):
            raise FSCResourceError("TalkBox snapshot response must be a JSON object")
        return payload