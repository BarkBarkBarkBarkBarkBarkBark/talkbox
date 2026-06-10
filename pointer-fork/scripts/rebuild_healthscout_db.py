# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2.0"]
# ///
"""Rebuild the Healthscout SQLite from the upstream HealthScout CSV.

Usage (from the repo root, uv installed):

    uv run backend/scripts/rebuild_healthscout_db.py \
        --csv  csv/HealthScout_9_18_2024.csv \
        --out  database/sacramento.db

Preprocessing follows the original Colab script:
 - rename X/Y -> longitude/latitude
 - normalize column names (lowercase, underscore, no punctuation)
 - strip + uppercase all text columns
 - normalize phone numbers to 1-XXX-XXX-XXXX
 - drop rows with missing telephone_number
 - write the resulting dataframe into SQLite table 'sacramento'
   (replacing the existing table in-place)

Designed to be idempotent: re-running overwrites the 'sacramento' table but
leaves any other tables in the .db alone.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd


def _standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", "_", regex=True)
        .str.replace(r"[^\w]", "", regex=True)
    )
    return df


def _standardize_phone(phone: object) -> object:
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 10:
        return f"1-{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"{digits[0]}-{digits[1:4]}-{digits[4:7]}-{digits[7:]}"
    return phone


def preprocess(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        csv_path,
        dtype={"Telephone Number": str},
        low_memory=False,
    )
    df.rename(columns={"X": "longitude", "Y": "latitude"}, inplace=True)
    df = _standardize_column_names(df)

    text_cols = df.select_dtypes(include=["object"]).columns
    df[text_cols] = df[text_cols].apply(lambda s: s.str.strip().str.upper())

    df["phone_number_for_transportation"] = df["phone_number_for_transportation"].apply(_standardize_phone)
    df["telephone_number"] = df["telephone_number"].apply(_standardize_phone)

    df.dropna(subset=["telephone_number"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def write_sqlite(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(out_path) as conn:
        df.to_sql("sacramento", conn, if_exists="replace", index=False)
        # A couple of helper indexes for the hot query pattern
        # (WHERE managedcareplan = ? AND pri_spec = ?)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_sacramento_mcp_spec "
            "ON sacramento(managedcareplan, pri_spec)"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to HealthScout CSV")
    parser.add_argument("--out", required=True, help="Destination SQLite file")
    args = parser.parse_args(argv)

    csv_path = Path(args.csv).resolve()
    out_path = Path(args.out).resolve()

    if not csv_path.exists():
        sys.exit(f"CSV not found: {csv_path}")

    print(f"Reading {csv_path} …", flush=True)
    df = preprocess(csv_path)
    print(f"Preprocessed rows: {len(df):,}", flush=True)

    print(f"Writing SQLite -> {out_path} …", flush=True)
    write_sqlite(df, out_path)
    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
