import logging

from fastapi import APIRouter, Depends, HTTPException

from src.infrastructure.persistence.database import User
from src.presentation.auth import optional_current_user
from src.presentation.query_runtime import get_query_handler
from src.presentation.schemas import (
    ErrorResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    ResultsPayload,
)

query_user_dep = optional_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse()


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["query"],
)
def process_user_query(
    payload: QueryRequest,
    user: User | None = Depends(query_user_dep),
) -> QueryResponse:
    logger.info("query from %s: %r", user.email if user else "anonymous", payload.query)
    try:
        result = get_query_handler().handle_query(payload.query)
        payload_data = result.get("results")
        results = ResultsPayload(**payload_data) if payload_data else None
        return QueryResponse(
            markdown=result.get("response", "No valid result found."),
            results=results,
        )
    except Exception as exc:
        logger.exception("query handling failed")
        raise HTTPException(status_code=500, detail=str(exc))
