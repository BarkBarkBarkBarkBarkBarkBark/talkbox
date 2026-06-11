from src.domain.services.query_healthscout import IQueryHealthscout


def _clean(value):
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _doctor_to_item(doctor) -> dict:
    transport = getattr(doctor, "transportation", None)
    return {
        "first_name": _clean(getattr(doctor, "first_name", None)),
        "last_name": _clean(getattr(doctor, "last_name", None)),
        "phone": _clean(getattr(doctor, "phone", None)),
        "specialty": _clean(getattr(doctor, "specialty", None)),
        "address": _clean(getattr(doctor, "address", None)),
        "insurance": _clean(getattr(doctor, "insurance", None)),
        "transportation_provider": _clean(getattr(transport, "provider", None)) if transport else None,
        "transportation_phone": _clean(getattr(transport, "telephone_number", None)) if transport else None,
    }


def _markdown_fallback(items: list[dict]) -> str:
    lines: list[str] = []
    for it in items:
        full = f"{it['first_name'] or ''} {it['last_name'] or ''}".strip() or "Provider"
        lines.append(f"**Dr. {full}**")
        if it["specialty"]:
            lines.append(it["specialty"])
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


class QueryHealthscoutService(IQueryHealthscout):
    def __init__(self, healthscout_db):
        self.healthscout_db = healthscout_db

    @staticmethod
    def _valid(value) -> bool:
        return value is not None and str(value).strip() != ""

    def query_healthscout(self, insurance: str, specialty: str) -> dict:
        doctors = self.healthscout_db.get_doctors_from_insurance_and_specialty(insurance, specialty)

        if not doctors and self._valid(insurance) and not self._valid(specialty):
            return {
                "response": (
                    f"No results for specialty: {specialty}.\n\n"
                    "Find a provider at https://www.healthcareoptions.dhcs.ca.gov/en/find-provider"
                ),
            }
        if not doctors and self._valid(specialty) and not self._valid(insurance):
            return {
                "response": (
                    f"No results for insurance: {insurance}.\n\n"
                    "Call Medi-Cal Health Care Options at (800) 430-4263 "
                    "(TTY: (800) 430-7077) to enroll in a Medi-Cal plan."
                ),
            }
        if not doctors:
            return {
                "response": (
                    f"No valid information for insurance ({insurance}) or "
                    f"specialty ({specialty}).\n\n"
                    "Call Medi-Cal Health Care Options at (800) 430-4263 "
                    "(TTY: (800) 430-7077) to enroll in a Medi-Cal plan."
                ),
            }

        items = [_doctor_to_item(d) for d in doctors]
        return {
            "response": _markdown_fallback(items),
            "results": {
                "type": "doctors",
                "category": "Healthscout",
                "items_doctors": items,
            },
        }
