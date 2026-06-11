from abc import ABC, abstractmethod

class IQueryHealthscout(ABC):
    @abstractmethod
    def query_healthscout(self, insurance: str, specialty: str) -> dict:
        """
        Given a insurance and doctor, executes the query on the Healthscout DB and returns the result.
        """
        pass