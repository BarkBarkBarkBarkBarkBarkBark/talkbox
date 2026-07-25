import asyncio

import httpx
import pytest
from pydantic import ValidationError

from src.application.services.resource_sync_service import ResourceSyncService
from src.infrastructure.config import Settings
from src.infrastructure.fsc_resource_client import (
    BootstrapSnapshot,
    ContentVersion,
    FSCResourceAuthError,
    FSCResourceClient,
)


def test_existing_fly_resource_api_key_is_supported(monkeypatch) -> None:
    monkeypatch.delenv("FSC_RESOURCE_API_KEY", raising=False)
    monkeypatch.setenv("FLY_RESOURCE_API_KEY", "existing-fly-key")

    assert Settings(_env_file=None).fsc_resource_api_key == "existing-fly-key"


def test_canonical_resource_api_key_takes_precedence(monkeypatch) -> None:
    monkeypatch.setenv("FSC_RESOURCE_API_KEY", "canonical-key")
    monkeypatch.setenv("FLY_RESOURCE_API_KEY", "existing-fly-key")

    assert Settings(_env_file=None).fsc_resource_api_key == "canonical-key"


def test_existing_replit_origin_url_is_supported(monkeypatch) -> None:
    monkeypatch.delenv("FSC_RESOURCE_API_BASE_URL", raising=False)
    monkeypatch.setenv("REPLIT_ORIGIN_URL", "https://resources.example.org")

    assert Settings(_env_file=None).fsc_resource_api_base_url == "https://resources.example.org"


def snapshot(version: int = 1, *, approved: bool = True) -> BootstrapSnapshot:
    return BootstrapSnapshot.model_validate(
        {
            "schema_version": "1",
            "content_version": version,
            "resources": [
                {
                    "id": "resource-1",
                    "name": "Community Clinic",
                    "description": "Free medical care",
                    "category": "Medical care",
                    "status": "published",
                    "created_by_user_id": "must-not-leave-upstream",
                    "contacts": [
                        {
                            "label": "Main",
                            "contact_type": "phone",
                            "value": "+1 (916) 555-0100",
                            "allow_talkbox_call": approved,
                        }
                    ],
                }
            ],
            "users": [{"email": "client@example.org"}],
            "participants": [{"name": "Private Person"}],
        }
    )


class FakeClient:
    def __init__(self, version: int, candidate: BootstrapSnapshot | Exception):
        self.version = version
        self.candidate = candidate
        self.bootstrap_calls = 0

    async def get_version(self) -> ContentVersion:
        return ContentVersion(content_version=self.version)

    async def get_bootstrap(self) -> BootstrapSnapshot:
        self.bootstrap_calls += 1
        if isinstance(self.candidate, Exception):
            raise self.candidate
        return self.candidate


def test_snapshot_keeps_only_public_resource_fields() -> None:
    candidate = snapshot()
    dumped = candidate.model_dump()

    assert "users" not in dumped
    assert "participants" not in dumped
    assert "created_by_user_id" not in dumped["services"][0]


def test_malformed_bootstrap_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BootstrapSnapshot.model_validate({"resources": [{"name": "Missing ID"}]})


@pytest.mark.asyncio
async def test_new_version_atomically_replaces_snapshot() -> None:
    service = ResourceSyncService()
    service._snapshot = snapshot(1)
    service._client = FakeClient(2, snapshot(2))

    assert await service.refresh() is True
    assert service.snapshot.content_version == 2


@pytest.mark.asyncio
async def test_same_version_avoids_bootstrap() -> None:
    service = ResourceSyncService()
    service._snapshot = snapshot(1)
    client = FakeClient(1, snapshot(1))
    service._client = client

    assert await service.refresh() is False
    assert client.bootstrap_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError(), FSCResourceAuthError("unauthorized")])
async def test_failed_refresh_preserves_last_known_good(error: Exception) -> None:
    service = ResourceSyncService()
    original = snapshot(1)
    service._snapshot = original
    service._client = FakeClient(2, error)

    assert await service.refresh() is False
    assert service.snapshot is original
    assert service.last_error_type == type(error).__name__


@pytest.mark.asyncio
async def test_empty_bootstrap_preserves_last_known_good() -> None:
    service = ResourceSyncService()
    original = snapshot(1)
    service._snapshot = original
    empty = BootstrapSnapshot(content_version=2)
    service._client = FakeClient(2, empty)

    assert await service.refresh() is False
    assert service.snapshot is original
    assert service.last_error_type == "ValueError"


@pytest.mark.asyncio
async def test_concurrent_refreshes_do_not_corrupt_snapshot() -> None:
    service = ResourceSyncService()
    client = FakeClient(2, snapshot(2))
    service._client = client

    await asyncio.gather(service.refresh(), service.refresh())

    assert service.snapshot.content_version == 2
    assert client.bootstrap_calls == 1


def test_only_explicitly_approved_contacts_are_callable() -> None:
    service = ResourceSyncService()
    service._snapshot = snapshot(1, approved=False)
    assert service.approved_agency("9165550100") is None

    service._snapshot = snapshot(2, approved=True)
    assert service.approved_agency("9165550100") == "Community Clinic"


@pytest.mark.asyncio
async def test_client_sends_bearer_key_without_logging_it(caplog) -> None:
    seen_authorization = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_authorization
        seen_authorization = request.headers.get("Authorization")
        return httpx.Response(200, json={"content_version": 7})

    client = FSCResourceClient("https://resources.example.org", "secret-service-key")
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://resources.example.org",
        headers={"Authorization": "Bearer secret-service-key"},
        transport=httpx.MockTransport(handler),
    )

    version = await client.get_version()
    await client.close()

    assert version.content_version == 7
    assert seen_authorization == "Bearer secret-service-key"
    assert "secret-service-key" not in caplog.text