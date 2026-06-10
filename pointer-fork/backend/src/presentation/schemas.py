from typing import Literal
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User's natural-language question")


class AgencyResult(BaseModel):
    """A single shelter / social-service row."""

    name: str
    phone: str | None = None
    address: str | None = None
    description: str | None = None
    insurance: str | None = None
    tags: str | None = None


class DoctorResult(BaseModel):
    """A single Healthscout provider row."""

    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    specialty: str | None = None
    address: str | None = None
    insurance: str | None = None
    transportation_provider: str | None = None
    transportation_phone: str | None = None


class ResultsPayload(BaseModel):
    """Structured payload attached to a QueryResponse.

    ``type`` tells the frontend which card layout to render.
    """

    type: Literal["agencies", "doctors"]
    category: str | None = None
    items_agencies: list[AgencyResult] = Field(default_factory=list)
    items_doctors: list[DoctorResult] = Field(default_factory=list)


class QueryResponse(BaseModel):
    markdown: str
    results: ResultsPayload | None = None


class ErrorResponse(BaseModel):
    error: str


class HealthResponse(BaseModel):
    status: str = "ok"
