import logging
import threading

from fastapi import APIRouter, Depends, Form, HTTPException, Response
from twilio.twiml.messaging_response import MessagingResponse

from src.application.services.query_handler import QueryHandler
from src.application.services.sms_async_response import SMSAsyncResponse
from src.infrastructure.healthscout_agent.healthscout_db_query import HealthScoutDB
from src.infrastructure.healthscout_agent.healthscout_extractor import HealthScoutExtractor
from src.infrastructure.healthscout_agent.query_healthscout_service import QueryHealthscoutService
from src.infrastructure.persistence.database import User
from src.infrastructure.sms.twilio_sms_service import TwilioSMSService
from src.infrastructure.sql_agent.sql_executor import SQLExecutor
from src.infrastructure.vector_store.pgvector_query_categorizer import PGVectorQueryCategorizer
from src.presentation.auth import optional_current_user

# No login wall: /api/query is open to anonymous users. The optional user is
# kept only so authenticated requests are still attributed in logs.
query_user_dep = optional_current_user
from src.presentation.schemas import (
    ErrorResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    ResultsPayload,
)

logger = logging.getLogger(__name__)

router = APIRouter()

pg_vector_categorizer = PGVectorQueryCategorizer()
sql_executor = SQLExecutor()
healthscout_db = HealthScoutDB()
healthscout_extractor = HealthScoutExtractor()
query_healthscout_service = QueryHealthscoutService(healthscout_db)

query_handler = QueryHandler(
    categorizer=pg_vector_categorizer,
    executor=sql_executor,
    hs_query=query_healthscout_service,
    hs_extract_info=healthscout_extractor,
)

sms_service = TwilioSMSService()
sms_async_service = SMSAsyncResponse(query_handler, sms_service)


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
        result = query_handler.handle_query(payload.query)
        payload_data = result.get("results")
        results = ResultsPayload(**payload_data) if payload_data else None
        return QueryResponse(
            markdown=result.get("response", "No valid result found."),
            results=results,
        )
    except Exception as e:
        logger.exception("query handling failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sms-query", tags=["sms"])
def sms_user_query(
    Body: str = Form(default=""),
    From: str = Form(default=""),
) -> Response:
    user_query = Body.strip()
    user_number = From.strip()

    twilio_resp = MessagingResponse()
    if not user_query:
        twilio_resp.message("Error: no message received.")
        return Response(content=str(twilio_resp), media_type="application/xml")

    twilio_resp.message("I'm working on your request, you'll receive the response shortly.")

    threading.Thread(
        target=sms_async_service.send_async_response,
        args=(user_query, user_number),
        daemon=True,
    ).start()

    return Response(content=str(twilio_resp), media_type="application/xml")
