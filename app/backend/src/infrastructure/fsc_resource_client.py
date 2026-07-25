"""Typed client for the FSC Resource Platform's public TalkBox API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class FSCResourceError(RuntimeError):
    """Base error for resource API failures."""


class FSCResourceAuthError(FSCResourceError):
    """The resource API rejected the service credential."""


class PublicResourceModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class ContentVersion(PublicResourceModel):
    content_version: str | int = Field(
        validation_alias=AliasChoices("content_version", "version")
    )
    generated_at: datetime | None = None


class ServiceContact(PublicResourceModel):
    label: str | None = None
    contact_type: str = "phone"
    value: str
    allow_call: bool = Field(
        default=False,
        validation_alias=AliasChoices("allow_call", "allow_talkbox_call"),
    )
    active: bool = True


class OrganizationService(PublicResourceModel):
    id: str
    name: str = Field(validation_alias=AliasChoices("name", "service_name"))
    description: str | None = Field(
        default=None,
        validation_alias=AliasChoices("description", "short_description"),
    )
    organization_name: str | None = None
    category: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    allow_call: bool = Field(
        default=False,
        validation_alias=AliasChoices("allow_call", "allow_talkbox_call"),
    )
    website_url: str | None = None
    hours_text: str | None = None
    eligibility_text: str | None = Field(
        default=None,
        validation_alias=AliasChoices("eligibility_text", "eligibility"),
    )
    languages_text: str | None = None
    status: str | None = None
    talkbox_visible: bool = True
    contacts: list[ServiceContact] = Field(default_factory=list)

    def approved_phone(self) -> str | None:
        for contact in sorted(self.contacts, key=lambda item: not item.allow_call):
            if contact.active and contact.allow_call and contact.contact_type == "phone":
                return contact.value
        if self.allow_call:
            return self.phone
        return None


class Announcement(PublicResourceModel):
    id: str
    title: str
    body: str
    priority: str | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None


class KioskProfile(PublicResourceModel):
    id: str
    name: str
    description: str | None = None
    enabled: bool = True
    service_ids: list[str] = Field(default_factory=list)


class BootstrapSnapshot(PublicResourceModel):
    schema_version: str = "1"
    content_version: str | int
    generated_at: datetime | None = None
    services: list[OrganizationService] = Field(default_factory=list)
    announcements: list[Announcement] = Field(default_factory=list)
    kiosk_profiles: list[KioskProfile] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def accept_resource_naming(cls, value: Any) -> Any:
        if isinstance(value, dict) and "services" not in value and "resources" in value:
            value = {**value, "services": value["resources"]}
        return value


class FSCResourceClient:
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
        return ContentVersion.model_validate(await self._get_json("/api/v1/talkbox/version"))

    async def get_bootstrap(self, kiosk_code: str | None = None) -> BootstrapSnapshot:
        params = {"kiosk_code": kiosk_code} if kiosk_code else None
        payload = await self._get_json("/api/v1/talkbox/bootstrap", params=params)
        return BootstrapSnapshot.model_validate(payload)

    async def _get_json(self, path: str, params: dict | None = None) -> dict:
        try:
            response = await self._client.get(path, params=params)
            if response.status_code in {401, 403}:
                raise FSCResourceAuthError("FSC Resource API authentication failed")
            response.raise_for_status()
            payload = response.json()
        except FSCResourceError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise FSCResourceError(type(exc).__name__) from exc
        if not isinstance(payload, dict):
            raise FSCResourceError("Upstream response must be a JSON object")
        return payload