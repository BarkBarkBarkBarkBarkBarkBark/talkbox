"""Read-only access to canonical TalkBox agencies in Postgres."""

from __future__ import annotations

from src.infrastructure.database import get_db_connection


class AgencyRepository:
    def list_directory(self) -> list[dict]:
        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT a.agency_name,
                       a.phone_number,
                       a.address,
                       a.description
                FROM agencies AS a
                WHERE a.show_on_kiosk = TRUE
                ORDER BY lower(a.agency_name), a.id;
                """
            )
            return [
                {
                    "name": row[0],
                    "phone": row[1],
                    "address": row[2],
                    "description": row[3],
                    "callable": bool(row[1]),
                }
                for row in cursor.fetchall()
            ]
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()
