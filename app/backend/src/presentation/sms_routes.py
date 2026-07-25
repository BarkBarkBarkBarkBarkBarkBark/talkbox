import logging

from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from src.presentation.query_runtime import get_query_handler

logger = logging.getLogger(__name__)

router = APIRouter()


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

    logger.info("sms query from %s: %r", user_number or "unknown", user_query)
    try:
        result = get_query_handler().handle_query(user_query)
        twilio_resp.message(result.get("response", "No valid result found."))
    except Exception:
        logger.exception("sms query handling failed")
        twilio_resp.message(
            "Sorry, something went wrong while processing your request."
        )

    return Response(content=str(twilio_resp), media_type="application/xml")
