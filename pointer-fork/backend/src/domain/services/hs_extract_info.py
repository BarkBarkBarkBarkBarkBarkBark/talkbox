from abc import ABC, abstractmethod

class IQueryHSExtract(ABC):
    @abstractmethod
    def extract_info(self, user_query: str) -> dict:
        """
        Given a query and a category, executes the query on the DB and returns the result.
        """
        pass