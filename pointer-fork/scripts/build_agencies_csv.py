"""Rebuild the backend seed data from the original Health Scout DBs CSVs.

Reads the source spreadsheets exported from the original Pointer project
(``PointerST/Health Scout DBs``) and regenerates:

  1. ``backend/src/infrastructure/seeds/agencies_master.csv`` — the master
     agency table consumed by ``seed_agencies()`` (TRUNCATE + INSERT, so the
     refresh is idempotent).
  2. ``backend/src/infrastructure/seeds/kiosk_mock_catalog.json`` — a snapshot
     of real resources per kiosk quick-category, used by the kiosk's offline /
     mock mode so demos show real agencies instead of hand-written samples.

Category names are normalized to the canonical names in
``seeds/query_categories/*.json`` (what the pgvector router emits and the SQL
executor matches on). Rows from the existing master whose category is not
covered by a dedicated source file are preserved, so the long tail (Hospital,
Urgent Care, Outreach, ...) survives a rebuild.

Usage:
    python scripts/build_agencies_csv.py [--source-dir PATH]
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEEDS_DIR = REPO_ROOT / "backend" / "src" / "infrastructure" / "seeds"
MASTER_CSV = SEEDS_DIR / "agencies_master.csv"
MOCK_JSON = SEEDS_DIR / "kiosk_mock_catalog.json"
DEFAULT_SOURCE_DIR = REPO_ROOT.parent / "PointerST" / "Health Scout DBs"

MASTER_COLUMNS = [
    "agency",
    "phone_number",
    "address",
    "category",
    "description",
    "insurance",
    "knowledge_tags",
]

# General_Resources.csv service_category values -> canonical category names
# (canonical = seeds/query_categories/*.json, matched by the SQL executor).
GENERAL_CATEGORY_MAP = {
    "all": "General",
    "elder": "Elder Services",
    "elders": "Elder Services",
    "food": "Food",
    "health": "Medical Clinic",
    "housing": "Housing",
    "irs": "IRS",
    "kids": "Youth",
    "legal": "Legal",
    "lgbtq": "LGBTQ",
    "men": "Shelter",
    "mental": "Mental Health Clinic",
    "money": "Payee",
    "motel": "Motel",
    "pets": "Animals",
    "phone": "LifeLine",
    "refugee": "Refugee",
    "respite": "Respite",
    "shelter": "Shelter",
    "transport": "Transport",
    "vets": "Veterans",
    "women": "Womens Shelter",
    "youth": "Youth",
}

# Legacy category names in older master files -> canonical names.
LEGACY_CATEGORY_MAP = {
    "Phone": "LifeLine",
}

# Categories fully regenerated from a dedicated source file: existing master
# rows in these categories are dropped before the fresh rows are merged in.
REPLACED_CATEGORIES = {
    "Medical Clinic",
    "Mental Health Clinic",
    "Mental Health Respite",
    "CalAIM Providers",
}

# Kiosk mock-mode quick categories (mirrors _MOCK_KEYWORDS in
# kiosk_query_service.py): catalog key -> canonical category.
MOCK_CATEGORIES = {
    "shelter": "Shelter",
    "food": "Food",
    "medical": "Medical Clinic",
    "mental_health": "Mental Health Clinic",
    "transport": "Transport",
    "veterans": "Veterans",
    "youth": "Youth",
}
MOCK_ITEMS_PER_CATEGORY = 4


def clean(value: str | None) -> str | None:
    """Trim, collapse whitespace, unescape HTML entities; empty -> None."""
    if value is None:
        return None
    text = html.unescape(html.unescape(str(value)))
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = " ".join(text.split())
    text = text.strip(" *").strip()
    return text or None


def clean_phone(value: str | None) -> str | None:
    """Keep the first plausible phone number, digits only."""
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) >= 10:
        return digits[:11] if digits.startswith("1") and len(digits) >= 11 else digits[:10]
    return digits or None


def read_csv(path: Path) -> list[dict]:
    """Read a CSV tolerating the cp1252 exports from the original project."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with path.open(newline="", encoding=encoding) as fh:
                return list(csv.DictReader(fh))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("all", b"", 0, 1, f"cannot decode {path}")


def row(agency, phone, address, category, description=None, insurance=None, tags=None):
    return {
        "agency": clean(agency),
        "phone_number": clean_phone(phone),
        "address": clean(address),
        "category": category,
        "description": clean(description),
        "insurance": clean(insurance),
        "knowledge_tags": clean(tags),
    }


# ─── Source loaders ──────────────────────────────────────────────────────────
def load_general_resources(src: Path) -> list[dict]:
    rows = []
    for r in read_csv(src / "General_Resources.csv"):
        raw_cat = (r.get("service_category") or "").strip().lower()
        category = GENERAL_CATEGORY_MAP.get(raw_cat)
        if not category or not clean(r.get("agency")):
            continue
        rows.append(
            row(r["agency"], r.get("phone"), r.get("address"), category, r.get("services"))
        )
    return rows


def load_medical_clinic(src: Path) -> list[dict]:
    return [
        row(r["agency"], r.get("phone_number"), r.get("address"), "Medical Clinic")
        for r in read_csv(src / "Medical_Clinic.csv")
        if clean(r.get("agency"))
    ]


def load_mh_clinic(src: Path) -> list[dict]:
    return [
        row(r["agency"], r.get("phone_number"), r.get("address"), "Mental Health Clinic", r.get("description"))
        for r in read_csv(src / "MH_Clinic.csv")
        if clean(r.get("agency"))
    ]


def load_mh_respite(src: Path) -> list[dict]:
    return [
        row(r["agency"], r.get("phone_number"), r.get("address"), "Mental Health Respite", r.get("description"))
        for r in read_csv(src / "MH_Respite.csv")
        if clean(r.get("agency"))
    ]


def load_calaim(src: Path) -> list[dict]:
    return [
        row(
            r["agency"],
            r.get("phone_number"),
            None,
            "CalAIM Providers",
            r.get("description"),
            insurance=r.get("insurance"),
        )
        for r in read_csv(src / "CALAIM_Providers.csv")
        if clean(r.get("agency"))
    ]


def load_rentals(src: Path) -> list[dict]:
    rows = []
    for r in read_csv(src / "Rentals.csv"):
        name = clean(r.get("apartment_project"))
        if not name:
            continue
        phone = r.get("project_phone_number") or r.get("managment_phone_number")
        rows.append(
            row(name, phone, r.get("address"), "Housing", "Affordable / subsidized apartment community.")
        )
    return rows


def load_existing_master() -> list[dict]:
    if not MASTER_CSV.exists():
        return []
    rows = []
    for r in read_csv(MASTER_CSV):
        if not clean(r.get("agency")):
            continue
        category = clean(r.get("category")) or "General"
        category = LEGACY_CATEGORY_MAP.get(category, category)
        rows.append(
            row(
                r.get("agency"),
                r.get("phone_number"),
                r.get("address"),
                category,
                r.get("description"),
                insurance=r.get("insurance"),
                tags=r.get("knowledge_tags"),
            )
        )
    return rows


# ─── Build ───────────────────────────────────────────────────────────────────
def build_master(source_dir: Path) -> list[dict]:
    fresh = (
        load_general_resources(source_dir)
        + load_medical_clinic(source_dir)
        + load_mh_clinic(source_dir)
        + load_mh_respite(source_dir)
        + load_calaim(source_dir)
        + load_rentals(source_dir)
    )
    preserved = [
        r for r in load_existing_master() if r["category"] not in REPLACED_CATEGORIES
    ]

    merged: dict[tuple, dict] = {}
    for r in preserved + fresh:
        key = ((r["agency"] or "").lower(), r["category"])
        existing = merged.get(key)
        if existing is None:
            merged[key] = r
        else:
            # Fresh rows win field-by-field; keep older values as fallback.
            for col in MASTER_COLUMNS:
                if r[col]:
                    existing[col] = r[col]

    return sorted(merged.values(), key=lambda r: (r["category"], (r["agency"] or "").lower()))


def build_mock_catalog(rows: list[dict]) -> dict:
    """Snapshot a few callable, real resources per kiosk quick-category."""
    by_category: dict[str, list[dict]] = {}
    for r in rows:
        by_category.setdefault(r["category"], []).append(r)

    catalog = {}
    for key, category in MOCK_CATEGORIES.items():
        candidates = [r for r in by_category.get(category, []) if r["phone_number"]]
        # Prefer entries that have a description (more useful on a 6" screen).
        candidates.sort(key=lambda r: (r["description"] is None, (r["agency"] or "").lower()))
        items = [
            {
                "name": r["agency"],
                "phone": r["phone_number"],
                "address": r["address"],
                "description": r["description"],
            }
            for r in candidates[:MOCK_ITEMS_PER_CATEGORY]
        ]
        if items:
            catalog[key] = {"category": category, "items": items}
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory containing the Health Scout DBs CSV exports",
    )
    args = parser.parse_args()

    if not args.source_dir.is_dir():
        print(f"source dir not found: {args.source_dir}", file=sys.stderr)
        return 1

    rows = build_master(args.source_dir)
    with MASTER_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MASTER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    catalog = build_mock_catalog(rows)
    MOCK_JSON.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    categories = sorted({r["category"] for r in rows})
    print(f"wrote {len(rows)} agencies across {len(categories)} categories -> {MASTER_CSV}")
    print(f"wrote mock catalog ({', '.join(sorted(catalog))}) -> {MOCK_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
