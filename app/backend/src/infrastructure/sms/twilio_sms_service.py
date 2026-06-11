from twilio.rest import Client

from src.infrastructure.config import settings


class TwilioSMSService:
    def __init__(self):
        self.client = Client(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
        )
        self.from_number = settings.twilio_phone_number

    def send_sms(self, to_number: str, message: str):
        self.client.messages.create(
            body=message,
            from_=self.from_number,
            to=to_number,
        )
