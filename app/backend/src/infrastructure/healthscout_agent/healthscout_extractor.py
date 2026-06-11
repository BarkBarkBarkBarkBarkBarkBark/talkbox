from src.domain.services.hs_extract_info import IQueryHSExtract
from src.infrastructure.healthscout_agent.healthscout_schema import MedicalSupportRequest
from src.infrastructure.healthscout_agent.prompt_template import prompt
from src.infrastructure.llm.factory import get_chat_llm


class HealthScoutExtractor(IQueryHSExtract):
    def __init__(self):
        llm = get_chat_llm()
        self.runnable = prompt | llm.with_structured_output(
            schema=MedicalSupportRequest, include_raw=False
        )

    def extract_info(self, text) -> MedicalSupportRequest:
        return self.runnable.invoke({"text": text})
