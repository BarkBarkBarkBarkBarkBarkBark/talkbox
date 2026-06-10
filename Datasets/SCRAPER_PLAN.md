# Pointer Data Collection Bot — Design & Implementation Plan

How to (re)collect every **necessary** Pointer source and rebuild the `doctors`
+ `agencies` tables. Source registry: [`manifest.yaml`](manifest.yaml).
Human overview: [`DATA_SOURCES.md`](DATA_SOURCES.md).

The bot is **not** a single BeautifulSoup script. Each source format gets the
right tool:

| Format | Tool | Sources |
| --- | --- | --- |
| HTML directories | **BeautifulSoup** + `requests` | CalAIM, 211 General Resources |
| Government data portals | **JSON API** (`requests`) | CMS Doctors, HCAI archive |
| PDF provider lists | **PDF_Analyzer** (pdfplumber + GPT-vision) | Medical/MH clinic, Respite |
| Spreadsheets | **pandas** | Rentals, enrichment lookups |

> BeautifulSoup is the right tool only for the HTML sources. Using it on the
> CMS file or the county PDFs would be fragile — those have proper APIs and a
> dedicated PDF pipeline respectively.

---

## Target folder layout

The bot reads/writes within `Datasets/` (created by
[`migrate_datasets.py`](migrate_datasets.py)):

Raw source files already live in the workspace (see `local_raw` in
[`manifest.yaml`](manifest.yaml)); the bot only needs to create `staging/` and
`build/` for its outputs:

```
Health Scout/
├── Pointer Databases/     # functional router DBs + enrichment + raw doctor sources (INPUT)
├── unnessecary/           # deduped twins + chaff (ignored)
└── Datasets/
    ├── manifest.yaml      # source registry (this drives everything)
    ├── DATA_SOURCES.md
    ├── SCRAPER_PLAN.md
    ├── migrate_datasets.py
    ├── reference_database/ # county provider PDFs + reference spreadsheets (INPUT)
    │   └── Therapy - Social Services/   # the LI-MHP / PEI / Respite PDFs
    ├── staging/           # normalized per-source CSVs (bot output — created on run)
    │   ├── doctors.csv  medical_clinic.csv  mh_clinic.csv
    │   ├── mh_respite.csv  calaim.csv  housing.csv  general.csv
    └── build/             # final artifacts (bot output — created on run)
        └── pointer.db     # doctors + agencies + category views
```

Fresh downloads land next to their existing copies (per `local_raw`); the bot
writes only into `staging/` and `build/`.


---

## Architecture: one fetcher per source

A small base class keeps each source honest. Every fetcher does three things —
`fetch` (raw → `sources/`), `parse` (raw → normalized rows), `validate` (sanity
checks) — then a shared loader merges `staging/` into `build/pointer.db`.

```python
# collector/base.py
from abc import ABC, abstractmethod
from pathlib import Path

class BaseFetcher(ABC):
    id: str            # matches manifest `id`
    category: str      # canonical Pointer category
    target_table: str  # "doctors" | "agencies"

    def __init__(self, root: Path):
        self.root = root
        self.raw_dir = root / "sources" / self.id
        self.staging = root / "staging"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.staging.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def fetch(self) -> Path: ...        # download -> returns raw path
    @abstractmethod
    def parse(self, raw: Path) -> list[dict]: ...   # -> normalized rows
    def validate(self, rows: list[dict]) -> None:   # override per source
        assert rows, f"{self.id}: produced zero rows"

    def run(self) -> Path:
        rows = self.parse(self.fetch())
        self.validate(rows)
        out = self.staging / f"{self.id}.csv"
        _write_csv(out, rows)
        return out
```

### Shared normalization contract

Reuse the rules already proven in `pointer-fork/scripts/`:

- **Column names** → lowercase, spaces→`_`, strip punctuation
  (`rebuild_healthscout_db.py::_standardize_column_names`).
- **Phones** → `1-XXX-XXX-XXXX`
  (`rebuild_healthscout_db.py::_standardize_phone`).
- **Text cleanup** → unescape HTML entities, collapse whitespace, smart-quotes →
  ASCII (`build_agencies_csv.py::clean` / `clean_phone`).
- **Agency category mapping** → `GENERAL_CATEGORY_MAP` in
  `build_agencies_csv.py` (211 `service_category` → canonical category).

Put these in `collector/normalize.py` and import everywhere so the bot and the
existing backend scripts stay byte-compatible.

---

## Per-source fetchers

### `cms_doctors` — JSON API (no scraping)
1. GET the metastore item:
   `https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/mj5m-pzi6?show-reference-ids`
2. Read `distribution[0].data.downloadURL` (rotating hash → resolve every run).
3. Stream-download `DAC_NationalDownloadableFile.csv` (large — use
   `requests` streaming or `pandas.read_csv(chunksize=...)`).
4. Filter `State == "CA"` and `City/Town` in the Sacramento set.
5. Join enrichment: `Primary Description` on `pri_spec`, `MCP Directory` +
   `Transportation Directory` on managed-care plan.
6. Normalize → `staging/doctors.csv`.

```python
import requests
META = ("https://data.cms.gov/provider-data/api/1/metastore/"
        "schemas/dataset/items/mj5m-pzi6?show-reference-ids")

def resolve_cms_url() -> str:
    item = requests.get(META, timeout=30).json()
    return item["distribution"][0]["data"]["downloadURL"]
```

**Validate:** row count > 1000; required columns present
(`npi, pri_spec, adr_ln_1, city/town, state, zip_code`).

### `dhcs_calaim` & `general_resources` — BeautifulSoup
The only true HTML scrapers.

```python
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "PointerDataBot/1.0 (+contact)"}

def soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")
```

- **CalAIM:** load the ECM/Community Supports page, collect links to per-plan
  provider rosters (`soup.select("a[href$='.xlsx'], a[href*='provider']")`),
  fetch each, parse HTML tables or XLSX, set `insurance` = plan name,
  `category` = "CalAIM Providers".
- **General (211):** iterate resource categories, extract agency name / phone /
  address / `service_category`, map via `GENERAL_CATEGORY_MAP`.

**Etiquette / safety:**
- Send a descriptive `User-Agent`; honor `robots.txt`.
- Rate-limit (≥1 req/sec, e.g. `time.sleep(1)`); retry with backoff.
- Treat all scraped HTML as untrusted input — never `eval`/exec it; only extract
  text. Validate phone/address shape before writing.
- ⚠️ **Confirm 211 / United Way redistribution terms before shipping** their
  data into the product.

### `sac_limhp_*` & `sac_mh_respite` — PDF via PDF_Analyzer
Reuse the cloned tool at `/Users/marco/talkbox/PDF_Analyzer`:

1. The current county PDFs live in
   `Datasets/reference_database/Therapy - Social Services/`; drop newer ones there.
2. Run `PDF_Analyzer/0-pdf2json.py` (pdfplumber extracts text; GPT-vision reads
   each page image into structured JSON). Needs `OPENAI_KEY` in `.env`.
3. Each page → `.json` + `.jpeg` pair for **manual verification** (the tool's
   README warns some pages render partially — eyeball them).
4. A thin adapter flattens the verified JSON into normalized agency rows →
   `staging/{medical_clinic,mh_clinic,mh_respite}.csv`.

```python
# collector/pdf_adapter.py — JSON (from PDF_Analyzer) -> agency rows
def json_to_agency_rows(json_path, category):
    import json
    data = json.loads(Path(json_path).read_text())
    return [
        {"agency": r.get("name"), "phone_number": r.get("phone"),
         "address": r.get("address"), "description": r.get("services"),
         "category": category, "source": json_path.parent.name}
        for r in data.get("records", [])
    ]
```

**Validate:** non-empty; every row has an agency name; phones parse.

### `affordable_housing` — pandas
`pd.read_excel(...)`, filter Sacramento County, map project + management phone →
one row, `category` = "Housing".

---

## Merge → `build/pointer.db`

```python
import sqlite3, pandas as pd
from pathlib import Path

AGENCY_SOURCES = ["medical_clinic", "mh_clinic", "mh_respite",
                  "calaim", "housing", "general"]

def build_db(root: Path):
    staging, out = root / "staging", root / "build" / "pointer.db"
    out.parent.mkdir(parents=True, exist_ok=True)

    doctors = pd.read_csv(staging / "doctors.csv")
    agencies = pd.concat(
        [pd.read_csv(staging / f"{s}.csv").assign(source=s) for s in AGENCY_SOURCES],
        ignore_index=True,
    )

    with sqlite3.connect(out) as cx:
        doctors.to_sql("doctors", cx, if_exists="replace", index=False)
        agencies.to_sql("agencies", cx, if_exists="replace", index=False)
        cx.executescript(VIEWS_SQL)
        cx.execute("CREATE INDEX IF NOT EXISTS ix_agencies_cat "
                   "ON agencies(category)")
        cx.execute("CREATE INDEX IF NOT EXISTS ix_doctors_spec "
                   "ON doctors(pri_spec)")
```

### Category views (unified table + views model)

```sql
-- VIEWS_SQL
CREATE VIEW IF NOT EXISTS view_medical_clinic AS
  SELECT * FROM agencies WHERE category = 'Medical Clinic';
CREATE VIEW IF NOT EXISTS view_mental_health AS
  SELECT * FROM agencies WHERE category = 'Mental Health Clinic';
CREATE VIEW IF NOT EXISTS view_mh_respite AS
  SELECT * FROM agencies WHERE category = 'Mental Health Respite';
CREATE VIEW IF NOT EXISTS view_calaim AS
  SELECT * FROM agencies WHERE category = 'CalAIM Providers';
CREATE VIEW IF NOT EXISTS view_housing AS
  SELECT * FROM agencies WHERE category = 'Housing';
CREATE VIEW IF NOT EXISTS view_general AS
  SELECT * FROM agencies
  WHERE category NOT IN ('Medical Clinic','Mental Health Clinic',
                         'Mental Health Respite','CalAIM Providers','Housing');
```

### De-duplication (the overlap problem)
Because the same agency can appear in multiple sources, de-dupe on a normalized
key **before** writing `agencies`:

```python
agencies["dedupe_key"] = (
    agencies["agency"].str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
    + "|" + agencies["phone_number"].fillna("").str.replace(r"\D", "", regex=True)
)
# keep richest row per key (most non-null fields), preserve all categories
agencies = (agencies
            .sort_values(by=agencies.columns.tolist(), key=lambda s: s.notna(), ascending=False)
            .drop_duplicates("dedupe_key"))
```

Keep `category`/`source` so a duplicate that legitimately spans categories is
preserved as separate category rows; only collapse true within-category dupes.

---

## Orchestration

```python
# collector/run.py
FETCHERS = [CmsDoctors, MedicalClinicPDF, MhClinicPDF, MhRespitePDF,
            CalAimScraper, GeneralResources211, AffordableHousing]

def main(root):
    for F in FETCHERS:
        f = F(root)
        try:
            print(f"[{f.id}] fetch+parse…")
            f.run()
        except Exception as e:                 # one source failing != all fail
            print(f"[{f.id}] FAILED: {e}")
    build_db(root)
```

Run individual sources during development; run all for a full refresh. Wire into
a monthly cron once stable (CMS is the only truly monthly source).

### Suggested dependencies
```
requests
beautifulsoup4
pandas
openpyxl          # xlsx
pdfplumber        # already used by PDF_Analyzer
pyyaml            # read manifest.yaml
```

---

## Verification checklist (per refresh)
1. `staging/doctors.csv` columns match the existing `HealthScout.csv` schema.
2. Each agency CSV: zero empty agency names; all phones match `^1?-?\d{10}$`.
3. `build/pointer.db` views each return > 0 rows.
4. Spot-check 5 random PDF-derived rows against the source PDF page (`.jpeg`).
5. Diff agency row counts vs. previous build; investigate large drops.

## Open items to confirm
- **County PDF URLs:** the `upstream` links in the manifest are the best-known
  landing pages; confirm they still host the current LI-MHP / PEI lists, or
  paste the exact PDF URLs and the manifest gets pinned.
- **Wiring:** these scripts can stay standalone in `Datasets/collector/`, or feed
  `pointer-fork`'s `rebuild_healthscout_db.py` / `agencies_master.csv` directly.
