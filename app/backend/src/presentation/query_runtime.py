from functools import lru_cache

from src.application.services.query_handler import QueryHandler
from src.infrastructure.healthscout_agent.healthscout_db_query import HealthScoutDB
from src.infrastructure.healthscout_agent.healthscout_extractor import HealthScoutExtractor
from src.infrastructure.healthscout_agent.query_healthscout_service import QueryHealthscoutService
from src.infrastructure.sql_agent.sql_executor import SQLExecutor
from src.infrastructure.vector_store.pgvector_query_categorizer import PGVectorQueryCategorizer

@lru_cache(maxsize=1)
def get_query_handler() -> QueryHandler:
    healthscout_db = HealthScoutDB()
    return QueryHandler(
        categorizer=PGVectorQueryCategorizer(),
        executor=SQLExecutor(),
        hs_query=QueryHealthscoutService(healthscout_db),
        hs_extract_info=HealthScoutExtractor(),
    )
