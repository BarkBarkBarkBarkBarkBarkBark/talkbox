from abc import ABC, abstractmethod

class IQueryExecutor(ABC):
    @abstractmethod
    def execute_query(self, user_query: str, category: str) -> dict:
        """
        Given a query and a category, executes the query on the DB and returns the result.
        """
        pass