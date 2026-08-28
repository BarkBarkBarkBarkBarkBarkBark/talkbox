import os
import uuid

import pytest
from fastapi import HTTPException
from starlette.requests import Request

os.environ.setdefault(
    "DB_URI", "postgresql+psycopg://talkbox:test@localhost:5432/talkbox"
)

from src.presentation import kiosk_call_routes, kiosk_device_auth, kiosk_device_routes


def make_request(headers: dict[str, str] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/api/kiosk/call/token",
            "headers": [
                (key.lower().encode("ascii"), value.encode("utf-8"))
                for key, value in (headers or {}).items()
            ],
            "query_string": b"",
        }
    )


def sample_device() -> kiosk_device_auth.KioskDevice:
    return kiosk_device_auth.KioskDevice(
        id=uuid.uuid4(),
        device_code="TB-001",
        display_name="Test kiosk",
        location="Test lab",
        enabled=True,
        revoked=False,
    )


def test_device_credential_hash_is_not_reusable_plaintext() -> None:
    credential = kiosk_device_auth.new_credential()
    encoded = kiosk_device_auth.hash_secret(credential)

    assert credential not in encoded
    assert kiosk_device_auth.verify_secret(credential, encoded)
    assert not kiosk_device_auth.verify_secret("wrong-credential", encoded)


def test_anonymous_device_status_is_public(monkeypatch) -> None:
    monkeypatch.setattr(kiosk_device_auth, "device_connection", lambda: pytest.fail("DB not needed"))

    status = kiosk_device_routes.device_status(make_request())

    assert status.enrolled is False
    assert status.calling_enabled is False


def test_localhost_appliance_can_call_without_enrollment(monkeypatch) -> None:
    monkeypatch.setattr(kiosk_device_auth.settings, "kiosk_calling_enabled", True)
    monkeypatch.setattr(kiosk_device_routes.settings, "kiosk_calling_enabled", True)
    monkeypatch.setattr(kiosk_device_auth, "device_connection", lambda: pytest.fail("DB not needed"))
    request = make_request({"Host": "localhost:8084"})

    device = kiosk_device_auth.require_kiosk_device(request)
    status = kiosk_device_routes.device_status(request)

    assert device.device_code == "TB-LOCAL"
    assert status.enrolled is True
    assert status.calling_enabled is True


def test_invalid_device_cookie_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(kiosk_device_auth, "_find_device", lambda credential: None)
    request = make_request({"Cookie": "talkbox_kiosk_device=invalid"})

    with pytest.raises(HTTPException) as error:
        kiosk_device_auth.require_kiosk_device(request)

    assert error.value.status_code == 403


def test_call_authorizing_routes_require_a_device_dependency() -> None:
    protected_paths = {"/kiosk/call/token", "/kiosk/call/start"}
    protected = [
        route for route in kiosk_call_routes.router.routes if route.path in protected_paths
    ]

    assert len(protected) == 2
    assert all(
        any(
            dependency.call is kiosk_device_auth.require_kiosk_device
            for dependency in route.dependant.dependencies
        )
        for route in protected
    )


def test_demo_mode_cannot_request_a_voice_token() -> None:
    with pytest.raises(HTTPException) as error:
        kiosk_call_routes.kiosk_call_token(
            kiosk_call_routes.KioskVoiceTokenRequest(phone="211"),
            make_request({"X-TalkBox-Mode": "demo"}),
            sample_device(),
        )

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_invalid_twilio_status_signature_is_rejected(monkeypatch) -> None:
    class FakeRequest:
        async def form(self):
            return {"CallSid": "CA123", "CallStatus": "completed"}

    monkeypatch.setattr(
        kiosk_call_routes,
        "_twilio_signature_valid",
        lambda request, form, path: False,
    )

    with pytest.raises(HTTPException) as error:
        await kiosk_call_routes.kiosk_call_status(FakeRequest())

    assert error.value.status_code == 403