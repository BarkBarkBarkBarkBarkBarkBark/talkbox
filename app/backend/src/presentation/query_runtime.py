from src.application.services.query_handler import QueryHandler
from src.infrastructure.healthscout_agent.healthscout_db_query import HealthScoutDB
from src.infrastructure.healthscout_agent.healthscout_extractor import HealthScoutExtractor
from src.infrastructure.healthscout_agent.query_healthscout_service import QueryHealthscoutService
from src.infrastructure.sql_agent.sql_executor import SQLExecutor
from src.infrastructure.vector_store.pgvector_query_categorizer import PGVectorQueryCategorizer

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
