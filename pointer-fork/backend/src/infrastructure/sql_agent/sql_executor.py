from src.domain.services.query_executor import IQueryExecutor
from src.infrastructure.database import get_db_connection


def _clean(value):
    """Trim strings, turn empty/None into None."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


class SQLExecutor(IQueryExecutor):
    def __init__(self):
        self.query_template = """
        SELECT agencies.agency_name,
               agencies.phone_number,
               agencies.address,
               agencies.description,
               agencies.insurance,
               agencies.knowledge_tags
        FROM agencies
        JOIN categories ON agencies.category_id = categories.id
        WHERE categories.name = %s
        ORDER BY RANDOM()
        LIMIT 5;
        """

    def _to_item(self, row) -> dict:
        return {
            "name": _clean(row[0]) or "Unknown agency",
            "phone": _clean(row[1]),
            "address": _clean(row[2]),
            "description": _clean(row[3]),
            "insurance": _clean(row[4]),
            "tags": _clean(row[5]),
        }

    def _format_markdown(self, items: list[dict]) -> str:
        """Human-readable fallback for clients that don't consume the structured
        payload. Kept short on purpose — the SPA renders cards."""
        lines: list[str] = []
        for it in items:
            lines.append(f"**{it['name']}**")
            if it["description"]:
                lines.append(it["description"])
            meta = []
            if it["phone"]:
                meta.append(f"📞 {it['phone']}")
            if it["address"]:
                meta.append(f"📍 {it['address']}")
            if it["insurance"]:
                meta.append(f"🛡 {it['insurance']}")
            if meta:
                lines.append(" · ".join(meta))
            lines.append("")
        return "\n".join(lines).strip()

    def execute_query(self, category: str) -> dict:
        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(self.query_template, (category,))
            rows = cursor.fetchall()

            if not rows:
                return {
                    "response": (
                        "No matching records found. Please call 211 "
                        "(916-498-1000) for social services."
                    ),
                }

            items = [self._to_item(r) for r in rows]
            return {
                "response": self._format_markdown(items),
                "results": {
                    "type": "agencies",
                    "category": category,
                    "items_agencies": items,
                },
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()
