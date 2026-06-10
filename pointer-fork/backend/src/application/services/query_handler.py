from src.domain.services.query_categorizer import IQueryCategorizer
from src.domain.services.query_executor import IQueryExecutor
from src.domain.services.query_healthscout import IQueryHealthscout
from src.infrastructure.healthscout_agent.query_healthscout_service import QueryHealthscoutService


class QueryHandler:
    def __init__(
        self,
        categorizer: IQueryCategorizer,
        executor: IQueryExecutor,
        hs_query: IQueryHealthscout,
        hs_extract_info: QueryHealthscoutService,
    ):
        self.categorizer = categorizer
        self.executor = executor
        self.hs_extract_info = hs_extract_info
        self.hs_query = hs_query

    def handle_query(self, user_query: str) -> dict:
        """Categorize the user query and dispatch to the right executor."""
        category = self.categorizer.retrieve_category(user_query)

        if category == "Healthscout":
            hs_extracted_info = self.hs_extract_info.extract_info(text=user_query)
            insurance, specialty = hs_extracted_info.insurance, hs_extracted_info.specialty

            if insurance is not None and specialty is not None:
                return self.hs_query.query_healthscout(insurance, specialty)
            fixed_category = "Medical Clinic"
            return self.executor.execute_query(fixed_category)
        return self.executor.execute_query(category)
