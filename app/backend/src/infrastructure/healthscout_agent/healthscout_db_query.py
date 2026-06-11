import os
import sqlite3

from src.infrastructure.config import settings
from src.infrastructure.healthscout_agent.healthscout_db_schema import Doctor, Trasportation


class HealthScoutDB:
    """SQLite accessor for the Healthscout dataset.

    A fresh connection is opened per call and closed afterwards, removing
    the need for Flask's request-scoped `g` container.
    """

    def __init__(self, db_name: str | None = None):
        self.db_name = db_name or settings.db_name

    def _connect(self) -> sqlite3.Connection:
        db_path = f"/data/{self.db_name}.db"
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found at {db_path}")
        return sqlite3.connect(db_path)

    def get_doctors_obj_from_query_results(self, cursor) -> list[Doctor]:
        doctors: list[Doctor] = []
        for row in cursor:
            doctors.append(
                Doctor(
                    first_name=row[4],
                    last_name=row[3],
                    managed_care_plan=row[2],
                    address=row[6],
                    pri_spec=row[10],
                    phone=row[11],
                    transportation=Trasportation(
                        telephone_number=row[7],
                        provider=row[8],
                    ),
                )
            )
        return doctors

    def get_doctors_from_insurance_and_specialty(self, insurance: str, specialty: str) -> list[Doctor]:
        query_sql = (
            "SELECT * FROM sacramento "
            "WHERE managedcareplan = ? AND pri_spec = ? "
            "ORDER BY RANDOM() LIMIT 4;"
        )
        conn = self._connect()
        try:
            cursor = conn.execute(query_sql, (insurance, specialty))
            return self.get_doctors_obj_from_query_results(cursor)
        finally:
            conn.close()
