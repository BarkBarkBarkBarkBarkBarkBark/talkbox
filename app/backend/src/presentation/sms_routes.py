import logging
import threading

from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from src.application.services.sms_async_response import SMSAsyncResponse
from src.infrastructure.sms.twilio_sms_service import TwilioSMSService
from src.presentation.query_runtime import query_handler

logger = logging.getLogger(__name__)

router = APIRouter()

sms_service = TwilioSMSService()
sms_async_service = SMSAsyncResponse(query_handler, sms_service)


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
