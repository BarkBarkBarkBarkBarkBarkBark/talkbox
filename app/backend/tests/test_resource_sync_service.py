import asyncio

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.application.services.resource_sync_service import ResourceSyncService
from src.infrastructure.config import Settings, settings
from src.infrastructure.fsc_resource_client import (
    BootstrapSnapshot,
    ContentVersion,
    FSCResourceAuthError,
    FSCResourceClient,
)
from src.infrastructure.talkbox_snapshot_client import ClientSnapshotClient
from src.presentation.resource_routes import _authorize_snapshot


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


def test_existing_kiosk_snapshot_key_is_supported(monkeypatch) -> None:
    monkeypatch.delenv("TALKBOX_CLIENT_SNAPSHOT_KEY", raising=False)
    monkeypatch.setenv("TALKBOX_KIOSK_SNAPSHOT_KEY", "existing-client-key")

    assert Settings(_env_file=None).talkbox_client_snapshot_key == "existing-client-key"


def test_client_role_uses_central_snapshot_source(monkeypatch) -> None:
    monkeypatch.setattr(settings, "fsc_resource_api_base_url", "")
    monkeypatch.setattr(settings, "fsc_resource_api_key", "")
    monkeypatch.setattr(settings, "talkbox_central_api_base_url", "https://talkbox.example.org")
    monkeypatch.setattr(settings, "talkbox_client_snapshot_key", "scoped-client-key")

    assert ResourceSyncService().upstream_source == "talkbox-central"


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


def test_live_fsc_service_shape_is_normalized() -> None:
    candidate = BootstrapSnapshot.model_validate(
        {
            "schema_version": "1",
            "content_version": 3,
            "services": [
                {
                    "id": "test-resource",
                    "organization_name": None,
                    "service_name": "Test Resource",
                    "short_description": ":)",
                    "phone": "707-637-6544",
                    "allow_call": True,
                    "eligibility": "Everyone",
                }
            ],
        }
    )

    service = candidate.services[0]
    assert service.name == "Test Resource"
    assert service.description == ":)"
    assert service.eligibility_text == "Everyone"
    assert service.approved_phone() == "707-637-6544"


def test_unapproved_direct_phone_is_not_exposed() -> None:
    service = ResourceSyncService()
    service._snapshot = BootstrapSnapshot.model_validate(
        {
            "content_version": 1,
            "services": [
                {
                    "id": "resource-1",
                    "service_name": "Food Pantry",
                    "short_description": "Emergency food",
                    "phone": "916-555-0100",
                    "allow_call": False,
                }
            ],
        }
    )

    _, items = service.query("food")
    assert items[0]["phone"] is None
    assert items[0]["callable"] is False


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
async def test_snapshot_is_restored_after_service_restart(tmp_path) -> None:
    cache_path = tmp_path / "resource-snapshot.sqlite3"
    first_service = ResourceSyncService(cache_path=cache_path)
    first_service._client = FakeClient(7, snapshot(7))

    assert await first_service.refresh() is True

    restarted_service = ResourceSyncService(cache_path=cache_path)
    assert await restarted_service.restore_cached_snapshot() is True
    assert restarted_service.snapshot == snapshot(7)
    assert restarted_service.last_successful_sync is not None


@pytest.mark.asyncio
async def test_corrupt_cache_is_preserved_before_recovery(tmp_path) -> None:
    cache_path = tmp_path / "resource-snapshot.sqlite3"
    cache_path.write_bytes(b"not a sqlite database")
    service = ResourceSyncService(cache_path=cache_path)

    assert await service.restore_cached_snapshot() is False
    assert not cache_path.exists()
    assert len(list(tmp_path.glob("resource-snapshot.sqlite3.corrupt-*"))) == 1

    service._client = FakeClient(3, snapshot(3))
    assert await service.refresh() is True
    assert cache_path.exists()


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


@pytest.mark.asyncio
async def test_client_checks_version_then_downloads_snapshot_with_scoped_key() -> None:
    seen_authorization = None
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count, seen_authorization
        request_count += 1
        seen_authorization = request.headers.get("Authorization")
        if request.url.path == "/api/kiosk/resource-version":
            return httpx.Response(200, json={"content_version": 9})
        return httpx.Response(200, json=snapshot(9).model_dump(mode="json"))

    client = ClientSnapshotClient("https://talkbox.example.org", "scoped-client-key")
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://talkbox.example.org",
        headers={"Authorization": "Bearer scoped-client-key"},
        transport=httpx.MockTransport(handler),
    )

    version = await client.get_version()
    candidate = await client.get_bootstrap()
    await client.close()

    assert version.content_version == 9
    assert candidate.content_version == 9
    assert request_count == 2
    assert seen_authorization == "Bearer scoped-client-key"


@pytest.mark.asyncio
async def test_client_skips_snapshot_download_when_version_is_unchanged() -> None:
    requested_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(200, json={"content_version": 9})

    client = ClientSnapshotClient("https://talkbox.example.org", "scoped-client-key")
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://talkbox.example.org",
        headers={"Authorization": "Bearer scoped-client-key"},
        transport=httpx.MockTransport(handler),
    )
    service = ResourceSyncService()
    service._snapshot = snapshot(9)
    service._client = client

    assert await service.refresh() is False
    await client.close()
    assert requested_paths == ["/api/kiosk/resource-version"]


def test_snapshot_route_requires_configured_scoped_key(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "talkbox_snapshot_publish_keys",
        "first-client-key, scoped-client-key",
    )

    with pytest.raises(HTTPException) as missing:
        _authorize_snapshot(None)
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException) as invalid:
        _authorize_snapshot("Bearer wrong-key")
    assert invalid.value.status_code == 401

    _authorize_snapshot("Bearer scoped-client-key")