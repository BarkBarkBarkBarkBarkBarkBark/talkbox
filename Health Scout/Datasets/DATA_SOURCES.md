# Pointer / Health Scout — Data Sources

Human-readable companion to [`manifest.yaml`](manifest.yaml). This is the
"why and where" for every dataset behind the Pointer router. The scraper bot
design is in [`SCRAPER_PLAN.md`](SCRAPER_PLAN.md); the folder reorganizer is
[`migrate_datasets.py`](migrate_datasets.py).

> **Region:** Sacramento County, CA
> **Canonical master:** `Pointer Databases/PointerDB.xlsx` (`.ods` mirror)

---

## How the data is organized

The Pointer router (`000 - Pointer.csv`) maps a user request to one **target
database**. Each target database is rebuilt from an authoritative upstream
source. Sources fall into three tiers:

| Tier | Meaning | Action |
| --- | --- | --- |
| **necessary** | Consumed by the live router | Refresh on a schedule |
| **enrichment** | Static lookup that decorates a table | Rarely changes |
| **archive** | Hospital/population analytics ("chaff") | Keep for reference, move out of the way |

### Data model: one searchable table + views

Agency-style sources overlap (a clinic can show up in the county MH list *and*
the 211 directory). Rather than seven disconnected tables or one giant flat
join, the rebuild merges all agency sources into a single **`agencies`** table
that carries `source` and `category` columns, then exposes per-category **SQL
views** on top. Doctors keep their own **`doctors`** table (different schema).

```
doctors            <- cms_doctors  (+ enrichment lookups)
agencies           <- medical / mh_clinic / mh_respite / calaim / housing / general
  └─ view_medical_clinic, view_mental_health, view_mh_respite,
     view_calaim, view_housing, view_general
```

**Why this over a flat join:** one query can return cross-source matches where
coverage overlaps (your stated concern), de-duplication happens in one place,
and category routing stays clean via views. The original
`000 - DB Join Script.docx` flat-table approach still works for export, but the
unified table is the source of truth.

---

## Necessary sources

### 1. Doctors — CMS Doctors & Clinicians National Downloadable File
- **Feeds:** `doctors` table (the "find a doctor" flow, ~17k Sacramento rows).
- **Why it matters:** clinician name, specialty, credential, telehealth flag,
  facility, and practice address — the backbone of HealthScout.
- **Category:** HealthScout
- **Format:** CSV (national file; filter to CA → Sacramento).
- **Download:** resolve at runtime from the CMS metastore (the URL embeds a
  content hash that rotates each refresh):
  - Resolver API: `https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/mj5m-pzi6?show-reference-ids`
  - JSON path: `distribution[0].data.downloadURL` → `DAC_NationalDownloadableFile.csv`
  - Landing page: https://data.cms.gov/provider-data/dataset/mj5m-pzi6
- **Cadence:** monthly (next refresh advertised ~the 11th).
- **Enriched by:** Primary Description (specialty→ailments), MCP Directory,
  Transportation Directory.
- **License:** Public domain (U.S. Government work).
- **Scraper type:** `cms_api` (JSON resolver, no HTML scraping needed).

### 2. Medical Clinics — Sacramento County / FQHC list
- **Feeds:** `agencies` (category **Medical Clinic**) — low/no-cost care for the
  uninsured.
- **Format:** PDF provider directory / XLSX export.
- **Upstream:** https://dhs.saccounty.gov/PRI/Pages/Primary-Health.aspx
- **Cadence:** irregular.
- **Scraper type:** `pdf_llm` — parse via the PDF_Analyzer pipeline.

### 3. Mental Health Clinics — Sacramento LI-MHP Medi-Cal directory
- **Feeds:** `agencies` (category **Mental Health Clinic**).
- **Why it matters:** therapist / psychiatric listings for uninsured + Medi-Cal.
- **Format:** PDF + DOCX.
- **Upstream:** https://dhs.saccounty.gov/BHS/Pages/Beneficiary-Services/GI-Provider-Directory.aspx
- **Scraper type:** `pdf_llm`.

### 4. MH Respite — Sacramento PEI & Respite list
- **Feeds:** `agencies` (category **Mental Health Respite**) — crisis / safe-place.
- **Format:** PDF.
- **Upstream:** https://dhs.saccounty.gov/BHS/Pages/Prevention-and-Early-Intervention/GI-PEI.aspx
- **Scraper type:** `pdf_llm`.

### 5. CalAIM Providers — DHCS ECM / Community Supports
- **Feeds:** `agencies` (category **CalAIM Providers**) — housing + Medi-Cal support.
- **Format:** HTML / XLSX per managed-care plan.
- **Upstream:** https://www.dhcs.ca.gov/CalAIM/ECM/Pages/Home.aspx
- **Cadence:** quarterly-ish.
- **Scraper type:** `html_bs4` — enumerate per-plan roster links, parse each.
  Carry the managed-care plan name into the `insurance` column.

### 6. Rentals — Affordable / tax-credit housing
- **Feeds:** `agencies` (category **Housing**).
- **Format:** XLSX.
- **Upstream:** CTCAC project lists https://www.treasurer.ca.gov/ctcac/projects.asp
  (secondary: SHRA https://www.shra.org/).
- **Cadence:** annual.
- **Scraper type:** `manual_xlsx` — filter to Sacramento County.

### 7. General Resources — FSC / 211 Sacramento
- **Feeds:** `agencies` (fallback; `service_category` fans out to shelter, food,
  legal, veterans, etc.).
- **Upstream:** https://www.211sacramento.org/211/
- **Scraper type:** `html_bs4`. `service_category` drives the canonical category
  mapping (see `GENERAL_CATEGORY_MAP` in
  `pointer-fork/scripts/build_agencies_csv.py`).
- **License:** ⚠️ verify 211 / United Way redistribution terms first.

### Router config (not a data table)
`000 - Pointer.csv` holds the routing keywords + few-shot examples. Keep it in
sync with `pointer-fork/.../seeds/query_categories/*.json`.

---

## Enrichment lookups (static)

| Source | Decorates | Join key | Purpose |
| --- | --- | --- | --- |
| Primary Description.csv | `doctors` | `pri_spec` | specialty → plain-language ailments (symptom search) |
| MCP Directory - Sacramento.parquet | `doctors` | `managed_care_plan` | Medi-Cal managed-care provider filter |
| Transportation Directory.xlsx | `doctors` | `managed_care_plan` | NEMT provider + phone + benefit text |

> **`MCP Directory` was reduced.** The upstream is the *statewide* DHCS Medi-Cal
> Managed Care provider directory (3.27 M rows, ~1.1 GB, all CA counties,
> geocoded). It has been filtered to the 312,822 Sacramento rows and stored as
> zstd parquet (**~6.5 MB — a 169× shrink**). The 1.1 GB statewide original was
> moved to `unnessecary/`.

---

## Archive (chaff — not router-consumed)

These are population/finance analytics. Useful for grants and research, but the
router never queries them. The migration script moves them to `archive/`.

| Source | What it is | Upstream |
| --- | --- | --- |
| HCAI Homeless Hospital Encounters | IP/ED counts for people experiencing homelessness | https://data.chhs.ca.gov/dataset/hospital-encounters-for-homeless-patients |
| HCAI Hospital Annual Financial Data | hospital finance reports | https://hcai.ca.gov/data-and-reports/cost-transparency/ |
| Discharge 2022 pivot / MS-DRG benchmark | discharge + DRG benchmarks | HCAI |

> Newer (2023–2024) vintages of the homeless-encounters data exist upstream via
> the CKAN API if you ever want to refresh the archive.

---

## Refresh cheat sheet

| Source | Type | Frequency | Effort |
| --- | --- | --- | --- |
| CMS Doctors | `cms_api` | monthly | automated (JSON resolver) |
| Medical / MH Clinic / Respite | `pdf_llm` | irregular | semi-auto (PDF_Analyzer + verify) |
| CalAIM | `html_bs4` | quarterly | automated (verify links) |
| Rentals | `manual_xlsx` | annual | manual export → parse |
| General (211) | `html_bs4` | continuous | automated (check terms) |
| Enrichment | static | rare | manual |
| Archive | `ckan_api` | annual | optional |
