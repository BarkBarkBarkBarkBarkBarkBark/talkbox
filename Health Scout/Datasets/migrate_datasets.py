#!/usr/bin/env python3
"""Audit + clean the realized Health Scout data layout.

The big reorg is already done. The folders now are:

    Health Scout/
    ├── Pointer Databases/   functional router DBs + enrichment + raw doctor sources
    ├── Datasets/            manifest + docs, leftover archive pivots
    │   └── reference_database/  county provider PDFs + reference spreadsheets
    └── unnessecary/         deduped format-twins + chaff (safe to delete wholesale)

This script no longer scaffolds anything. It (1) reports the current layout and
(2) proposes moving the remaining non-functional cruft out of
``Pointer Databases/`` into ``unnessecary/`` so the folder holds only the
data the Pointer router actually uses.

SAFE BY DEFAULT: no flags = DRY RUN (prints the plan only). Pass --apply to move.
Nothing is deleted; moves use shutil.move and skip any existing destination.

Usage:
    python migrate_datasets.py            # dry run
    python migrate_datasets.py --apply    # perform the moves
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# This file lives in Health Scout/Datasets/ ; data folders are siblings.
DATASETS_DIR = Path(__file__).resolve().parent
HEALTH_SCOUT = DATASETS_DIR.parent
POINTER_DB = HEALTH_SCOUT / "Pointer Databases"
UNNESSECARY = HEALTH_SCOUT / "unnessecary"
REFERENCE = DATASETS_DIR / "reference_database"

# Files the Pointer router DOES use — never move these.
FUNCTIONAL = {
    "000 - Pointer.csv",
    "HealthScout.csv",
    "Medical_Clinic.csv", "MH_Clinic.csv", "MH_Respite.csv",
    "CALAIM_Providers.csv", "Rentals.csv", "General_Resources.csv",
    "PointerDB.xlsx", "PointerDB.ods",
    # enrichment lookups
    "Primary Description.csv", "MCP Directory.csv", "Transportation Directory.xlsx",
}

# Raw / intermediate SOURCES — useful for rebuilds; keep, but they could later
# move to reference_database/. Left in place for now (not chaff).
SOURCES = {
    "CMS- National Directory of Doctors & clinicians.csv",
    "Doctor Directory.csv", "Clinic Directory.csv",
    "HealthScout_9_18_2024.xlsx", "HealthScoutDatabase.csv",
    "Preprocessed-HealthScoutDatabase-08-10-24.csv",
    "Sacramento Doctors Big 4 Insurances.xlsx",
    "Health-Centers-09-18-2024.xlsx", "Affordable Housing.xlsx",
    "Geo.xlsx", "Ride Scheduling Data.xlsx",
}

# Non-data files still sitting in Pointer Databases/. Two destinations so that
# nothing valuable lands in a folder the user may delete wholesale:
#   DISPOSABLE -> unnessecary/   (business/marketing; safe to delete)
#   REFERENCE  -> reference_database/  (technical docs worth keeping)
DISPOSABLE = {
    "Economic Analysis.docx",
    "Health Scout Business Plan.docx",
    "HealthScout.pdf",
    "Healthscout Access Card.pdf",
}
REFERENCE_DOCS = {
    "000 - DB Join Script.docx",
    "SQL_.docx",
    "Health scout script & prompt.docx",
    "000 - CAS Resource Book.xlsx",
}
CHAFF = DISPOSABLE | REFERENCE_DOCS


def report(root: Path) -> None:
    print(f"• {root.name}/ contents")
    for child in sorted(root.iterdir()):
        name = child.name
        if name == ".DS_Store":
            continue
        if name in FUNCTIONAL:
            tag = "functional"
        elif name in SOURCES:
            tag = "source    "
        elif name in CHAFF:
            tag = "chaff     "
        else:
            tag = "unclassif."
        print(f"    [{tag}] {name}")


def plan_moves(apply: bool) -> int:
    print("• relocate non-data files")
    moved = 0
    for name in sorted(CHAFF):
        dest_dir = UNNESSECARY if name in DISPOSABLE else REFERENCE
        src = POINTER_DB / name
        if not src.exists():
            print(f"    skip (missing)  {name}")
            continue
        dst = dest_dir / name
        if dst.exists():
            print(f"    skip (exists)   {name}")
            continue
        print(f"    move            {name}  ->  {dest_dir.name}/")
        if apply:
            dest_dir.mkdir(exist_ok=True)
            shutil.move(str(src), str(dst))
        moved += 1
    return moved


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="perform moves (default: dry run)")
    args = ap.parse_args(argv)

    if not POINTER_DB.is_dir():
        sys.exit(f"not found: {POINTER_DB}")

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"=== cleanup [{mode}]  Pointer Databases -> unnessecary / reference_database\n")
    report(POINTER_DB)
    print()
    moved = plan_moves(args.apply)
    print(f"\n{'moved' if args.apply else 'would move'} {moved} item(s).")
    if not args.apply:
        print("Re-run with --apply to perform these moves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
