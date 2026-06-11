import uuid

from fastapi_users import schemas
from pydantic import Field


class UserRead(schemas.BaseUser[uuid.UUID]):
    name: str
    company: str | None = None


class UserCreate(schemas.BaseUserCreate):
    name: str = Field(..., min_length=1, max_length=255)
    company: str | None = Field(default=None, max_length=255)


class UserUpdate(schemas.BaseUserUpdate):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    company: str | None = Field(default=None, max_length=255)
