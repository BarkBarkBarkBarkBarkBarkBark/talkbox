from abc import ABC, abstractmethod

class IQueryCategorizer(ABC):
    @abstractmethod
    def retrieve_category(self, user_query: str, k: int = 1) -> str:
        """
        Given a user query, returns the relevant category.
        """
        pass