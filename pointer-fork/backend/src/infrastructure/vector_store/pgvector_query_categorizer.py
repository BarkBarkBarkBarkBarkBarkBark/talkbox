import logging

from langchain_postgres import PGVector

from src.domain.services.query_categorizer import IQueryCategorizer
from src.infrastructure.config import settings
from src.infrastructure.llm.factory import get_embeddings

logger = logging.getLogger(__name__)


class PGVectorQueryCategorizer(IQueryCategorizer):
    def retrieve_category(self, user_query: str, k: int = 1) -> str:
        if not user_query or not isinstance(user_query, str):
            logger.warning("invalid query input")
            return "Error: user query Unknown"
        vector_store = None
        try:
            vector_store = PGVector(
                embeddings=get_embeddings(),
                collection_name=settings.collection_name,
                connection=settings.db_uri,
                use_jsonb=True,
            )
            results = vector_store.similarity_search(user_query, k=k)
            result_var = results[0].metadata.get("category", "Unknown")
            logger.debug("category found: %s", result_var)
            return result_var
        except Exception:
            logger.exception("categorizer failed")
            return "Unknown"
        finally:
            if vector_store is not None:
                del vector_store
