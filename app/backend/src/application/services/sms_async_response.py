import logging

from src.application.services.query_handler import QueryHandler
from src.infrastructure.sms.twilio_sms_service import TwilioSMSService

logger = logging.getLogger(__name__)


class SMSAsyncResponse:
    def __init__(self, query_handler: QueryHandler, sms_service: TwilioSMSService):
        self.query_handler = query_handler
        self.sms_service = sms_service

    def send_async_response(self, user_query: str, user_number: str):
        try:
            logger.debug(f"Handling async response for query: {user_query}")
            result = self.query_handler.handle_query(user_query)
            query_result = result.get("response", "No result found.")
            logger.debug(f"Query result: {query_result}")
            self.sms_service.send_sms(user_number, query_result)
            logger.info(f"SMS sent to {user_number}")
        except Exception as e:
            logger.error(f"Error in send_async_response: {e}")
