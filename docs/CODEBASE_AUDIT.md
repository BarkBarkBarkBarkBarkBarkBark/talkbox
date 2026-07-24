# TalkBox Codebase Audit and Simplification Review Packet

Date: 2026-07-23

Audit branch: `dev`

Known-good starting commit: `a9aaa21a1c3eddefdc09e3beed1693df80e750aa`

This document is an audit and migration plan. It is not evidence that the proposed architecture has been deployed.

## How to read this packet

- **OBSERVED** means confirmed in source, configuration, or a read-only live check.
- **RUNNING NOW** means behavior in the containers currently serving the physical Raspberry Pi.
- **IN-PROGRESS DEV CHANGE** means an uncommitted change on `dev`; it is not running on the Pi.
- **RECOMMENDATION** means proposed work that has not been implemented.
- **UNKNOWN** means an operational fact still needing human or deployment-system confirmation.

The distinction matters. The checked-out source has safety changes that the four-day-old running backend image does not have.

# Executive summary

TalkBox is a React kiosk and FastAPI service that classifies a request, selects local resources, and can place calls through Twilio. The physical kiosk currently runs frontend, backend, and PostgreSQL/pgvector containers on one Raspberry Pi.

The codebase's main risk is not its size. It is that several different things can look authoritative:

- `agencies_master.csv`
- local PostgreSQL
- Neon PostgreSQL
- `kiosk_mock_catalog.json`
- category vectors in LangChain-managed tables
- the HealthScout SQLite database

The current running backend can silently replace a failed real query with mock records. Its startup path can also replace all agency and category rows from CSV. A health endpoint can report `ok` while the database or embedding path is broken. Resource ordering is random.

Neon project `soft-hat-27629835` in organization `org-super-sunset-88688178` is provisioned and populated. A read-only comparison showed that its 379 agencies and 29 categories exactly match the Pi catalog. Neon also has 30 `query_categories` vectors. However, Neon is **not yet the production authority** because the running kiosk still queries its local database.

The minimum target architecture is:

```text
Human editors
      |
      v
Authenticated /admin/resources
      |
      v
Central FastAPI on Fly
      |
      v
Canonical Neon PostgreSQL + pgvector
      |
      +-----------------------------+
      |                             |
      v                             v
Online kiosk query API       Versioned SQLite snapshot
                                    |
                                    v
                         Last-known-good offline query
```

Vectors, model credentials, edits, and semantic ranking remain central. Each kiosk receives only a read-only, checksummed SQLite catalog for T-Mobile outages. A kiosk must never import, vectorize, or overwrite canonical resource data.

# 1. Architecture map

## Current physical-kiosk architecture

```text
USB keypad / touchscreen / Tonor microphone / P10S speaker
                         |
                         v
              Chromium kiosk on Raspberry Pi
                         |
                         v
               nginx + React/Vite frontend
                  127.0.0.1:8084
                         |
                         v
                    FastAPI backend
                  127.0.0.1:8085
                  /       |       \
                 /        |        \
        OpenAI/Bedrock   Twilio    local persistence
        embeddings/LLM  Voice/SMS      |
                                      +--------------------+
                                      |                    |
                                      v                    v
                              local PostgreSQL       HealthScout SQLite
                              + pgvector volume      sacramento.db
```

## Component inventory

| Component | Why it exists | Production use today | State owner | Simplification judgment |
| --- | --- | --- | --- | --- |
| React/Vite frontend | Kiosk, chat, and authenticated web UI | Yes | Browser state only | **KEEP**, preserve UX while simplifying APIs |
| nginx frontend container | Serves built frontend and proxies `/api` | Yes | None | **KEEP** on kiosks unless central hosting makes it redundant |
| FastAPI backend | Query orchestration, auth, STT, Twilio, kiosk configuration | Yes | Mostly stateless, but currently performs startup writes | **KEEP**, make runtime non-mutating |
| Local PostgreSQL/pgvector | Agencies, categories, users, category vectors | Yes, on the Pi | Pi Docker volume | **DELETE LATER** as kiosk authority after central/offline cutover |
| Neon PostgreSQL/pgvector | Intended canonical store | Populated, not yet serving kiosks | Neon project | **KEEP**, make sole authority |
| HealthScout SQLite | Provider lookup by insurance/specialty | Possibly; usage not proven | Bundled file or `/data` override | **UNKNOWN**, measure before merge/delete |
| OpenAI embeddings | Maps natural language to one of 29 categories | Yes in real query path | External provider | **KEEP INITIALLY**, centralize and reassess later |
| Bedrock provider path | Alternate chat/embedding provider | No confirmed production use | AWS | **UNKNOWN**, remove if unsupported |
| Twilio Voice/SMS | Kiosk calls and SMS query response | Voice is core; SMS status unclear | Twilio + backend config | **KEEP Voice**, verify SMS requirement |
| Local whisper.cpp STT | Voice input without network transcription | Yes/configured | Model file on Pi | **KEEP** while it meets hardware quality needs |
| FastAPI Users auth | Existing web authentication | Yes | PostgreSQL `users` | **KEEP**, do not add another auth platform |
| Docker Compose | Reproducible local appliance stack | Yes | Pi filesystem and volumes | **KEEP**, reduce services after cutover |
| Fly configuration | Candidate central backend host | Present, use not yet confirmed live | Fly | **KEEP/VERIFY**, preferred central host |
| Vercel entrypoints/config | Historical serverless/web deployment | Some compatibility code remains | Vercel | **UNKNOWN**, verify before deletion |
| Tailscale/Funnel | Remote reachability and possible Twilio webhook publication | Configured conditionally | Pi/Fly runtime state | **VERIFY**, retain only if still required after Fly cutover |

# 2. Exact kiosk query paths

## Quick-resource button

1. The menu is returned by `app/backend/src/presentation/kiosk_core_routes.py` as `_HOME_MENU`.
2. `app/frontend/src/hooks/useKioskStateMachine.js` receives the menu and handles a `QUICK_QUERY` entry.
3. `selectMenuEntry()` calls `runQuery(entry.query)`, for example `I need shelter tonight`.
4. `app/frontend/src/lib/kioskApi.js` sends `POST /api/kiosk/query`.
5. `app/backend/src/presentation/kiosk_core_routes.py` validates the request and calls `KioskQueryService.query()`.
6. `app/backend/src/application/services/kiosk_query_service.py` either enters mock mode or calls `_run_structured_query()`.
7. `app/backend/src/infrastructure/vector_store/pgvector_query_categorizer.py` embeds the query and performs top-one similarity search in `query_categories`.
8. The resulting category is passed to `app/backend/src/infrastructure/sql_agent/sql_executor.py`.
9. `SQLExecutor` joins `agencies` to `categories`, currently uses `ORDER BY RANDOM()`, and returns up to five records.
10. `KioskQueryService._normalize()` produces numbered items, spoken summary, and the 211 fallback.
11. The state machine stores the response and kiosk components render resource cards.

## Spoken or typed natural-language request

1. The Ask screen is driven by `useKioskStateMachine.js` and kiosk components under `app/frontend/src/components/kiosk/`.
2. Voice input is recorded in the browser and sent by `kioskApi.transcribeAudio()` to `POST /api/kiosk/speech/transcribe`.
3. `app/backend/src/application/services/kiosk_stt_service.py` uses local whisper.cpp, OpenAI, or the configured fallback mode.
4. The transcript is returned to the frontend for confirmation/submission.
5. Typed text or accepted transcript is sent to the same `POST /api/kiosk/query` path.
6. From that point, categorization, SQL lookup, normalization, and rendering are identical to the quick-resource path.

## HealthScout branch

The general query runtime in `app/backend/src/presentation/query_runtime.py` can route a `Healthscout` category through an LLM extractor and `app/backend/src/infrastructure/healthscout_agent/healthscout_db_query.py`. The kiosk query service deliberately converts `Healthscout` to `Medical Clinic` instead of performing LLM specialty extraction in the immediate kiosk path. This parallel behavior should be documented in tests before consolidation.

# 3. When mock data is used

**OBSERVED:** `KioskQueryService.query()` uses `kiosk_mock_catalog.json` in two cases:

1. `KIOSK_MOCK_QUERY=true`.
2. Any exception escapes the real structured query path.

The catch is `except Exception`, so mock data can replace failures from:

- missing or invalid embedding credentials
- OpenAI/Bedrock outage
- database/network outage
- absent or incompatible pgvector collection
- schema mismatch
- SQL error
- programming error in the query path

The backend logs an exception but returns a normal-looking result. The kiosk user is not told that the agencies came from a fixture.

**RUNNING NOW:** `KIOSK_MOCK_QUERY=false`, but broad exception fallback is active. Therefore the physical kiosk normally queries local Postgres and can silently display mock records when the real pipeline fails.

**RECOMMENDATION:** Production behavior must be:

```text
central query succeeds -> real results with source and catalog version
central query unavailable -> last-known-good local snapshot
snapshot unavailable/no confident match -> explicit unavailable state + Call 211
programming/validation error -> explicit error, never fallback as success
```

Every query response should expose non-secret provenance such as `central-neon` or `local-snapshot` and a catalog version.

# 4. Every current source of resource truth

| Data | Current authority | Generated from | Runtime consumer | Should remain? |
| --- | --- | --- | --- | --- |
| Local `agencies` and `categories` | **RUNNING authority** | `agencies_master.csv` plus any manual DB changes until next seed | SQLExecutor, call allowlist | Remove as kiosk authority after cutover |
| Neon `agencies` and `categories` | Exact populated copy, intended authority | Migrated/imported catalog | Not yet the running kiosk query source | **KEEP; become sole authority** |
| `agencies_master.csv` | Startup/import authority in committed behavior | Historical source aggregation | Agency seeder | Keep only as import fixture/archive |
| `kiosk_mock_catalog.json` | Runtime fallback fixture | Curated/generated subset of CSV | KioskQueryService | Remove from production runtime; test fixture only or delete |
| `query_categories/*.json` | Category-routing seed inputs | Hand-authored examples | Vector seeder | Keep as versioned routing input if vector routing remains |
| `langchain_pg_collection` / `langchain_pg_embedding` | Runtime category-vector store | Category JSON + embedding model | PGVector categorizer | Keep centrally; never build on kiosks |
| Proposed `agency_catalog_vN` vectors | In-progress design, not built in production | Canonical Neon agency content | Future central semantic retrieval | Keep centrally with model/hash metadata |
| `database/sacramento.db` | Provider facts for HealthScout | Historical HealthScout datasets | HealthScoutDB | Unknown; migrate or delete after usage/data review |
| `Datasets/` | Raw/reference inputs | External source collection | Scripts/humans, not direct kiosk runtime | Keep as provenance/staging, not authority |
| `resource_import_batches/rows` in Neon | Import staging/audit | External import workflow | Future operator workflow | Keep if migration `003` is recovered into repo |
| Hardcoded 211 resource | Code constant | Manual | Kiosk fallback and call routing | Keep one controlled configuration source |
| Hardcoded home menu/categories | Backend constants and duplicate legacy route | Manual | Kiosk UI | Keep one active definition; delete duplicate legacy definition |

## Practical answer today

If a phone number is corrected only in local PostgreSQL, the correction can be lost when the running backend restarts and reloads CSV. If corrected only in CSV, Neon and a currently running database do not update automatically. If corrected only in Neon, the kiosk does not see it yet.

Therefore there is no safe single editing location today. This is a critical operational gap.

# 5. Database lifecycle audit

## Committed behavior at the known-good starting commit

1. `docker-entrypoint.sh` starts optional Tailscale behavior.
2. Unless `TALKBOX_SKIP_BOOTSTRAP=1`, it runs `python main.py seed`.
3. `main.py` runs Alembic migrations.
4. Category vectors are seeded or skipped based on collection count.
5. `agency_seeder.py` executes `TRUNCATE agencies, categories RESTART IDENTITY CASCADE` and reloads CSV rows in one transaction.
6. Uvicorn starts.
7. FastAPI lifespan calls `seed_admin()` and continues even if it fails.

The agency transaction is atomic, but it is destructive. Calling it idempotent only means repeated runs converge on CSV content; it does not preserve human edits.

## Running physical Pi

**RUNNING NOW:** Three healthy containers have been up for roughly four days:

- `talkbox-frontend`
- `talkbox-backend`
- `talkbox-postgres`

The running backend predates the uncommitted `dev` safety edits. Restarting or recreating that backend can invoke the destructive startup sequence.

Persistent local state:

- `talkbox-postgres-data`: local agencies, categories, users, and vectors
- `talkbox-backend-data`: `/data` logs/model or SQLite overrides
- `app/.env`: local secrets/configuration
- files outside the repo under `/etc`, `/usr/local/bin`, and user configuration for kiosk startup/audio

## In-progress dev behavior

The uncommitted `dev` changes:

- remove seed/migration work from `docker-entrypoint.sh`
- remove the aggregate `seed` command
- require `seed-agencies --confirm-replace`
- split category-vector and agency-vector commands
- make agency vector builds target a fresh versioned collection
- make `install.sh` initialize only an empty local catalog

These changes built successfully in an isolated image. They have not been deployed to the Pi.

## Fresh install after the dev changes

The transitional installer starts Postgres, runs Alembic explicitly, checks agency count, initializes only an empty database, then starts application services. This protects populated local installations but is not the final kiosk architecture. Once kiosks consume the central API plus snapshots, new kiosk installation should not create local Postgres at all.

## Update and restart

The root `talkbox` CLI and `talkbox-stack.service` use the root Compose project. `talkbox update` pulls code, rebuilds/recreates services, waits for health, synchronizes Twilio as configured, and reloads Chromium. Recreating the old backend is dangerous because its entrypoint seeds. A plain `talkbox restart` also restarts containers and can trigger entrypoint behavior.

Never use:

- `docker compose down -v`
- `docker volume rm talkbox-postgres-data`
- destructive volume prune operations
- catalog replacement commands against Neon production

# 6. Live database facts and migration drift

## Local Pi

Read-only checks confirmed:

- 379 agencies
- 29 categories
- 30 vectors in `query_categories`
- local host `talkbox-postgres`

A validated custom-format dump exists outside the repository:

```text
/home/operator/talkbox-backups/20260724T012800Z-a9aaa21/talkbox-local.dump
SHA-256: 8f973beb9c541149a807fa2393cf2269cb1ba3ef8a1959431f3eb4355abb8e2c
Archive entries: 34
```

## Neon

Read-only pooled SQL checks confirmed:

- database `neondb`
- PostgreSQL 18.4
- extensions `vector`, `pg_session_jwt`, `plpgsql`
- Alembic revision `003_resource_import_staging`
- 379 agencies
- 29 categories
- one user
- zero import batches/rows
- 30 vectors in `query_categories`

A deterministic full export of agency and category fields matched local Postgres exactly:

```text
SHA-256: 0158f0683d65b71b0bc6d2fbe1c6cfc44d90952bd4489f5c192da681d4f88ad7
local == Neon: yes
```

## Drift finding

**HIGH:** Neon reports migration `003_resource_import_staging`, but this repository contains only `001_initial.py` and `002_users_table.py`. The production schema cannot currently be reproduced from repository migrations alone.

Before another schema change, recover the exact `003` migration from the branch, commit, deployment artifact, or migration author. Do not invent a replacement solely from the live table shape without documenting provenance.

# 7. Complexity inventory

| Classification | Item | Reason |
| --- | --- | --- |
| **KEEP** | `core_api.py` | Active FastAPI composition root |
| **KEEP** | `presentation/api.py` | Active Uvicorn re-export target from `main.py`; not dead |
| **KEEP** | `query_runtime.py` | Active object graph for general query routes |
| **KEEP** | Twilio call routes/service | Core kiosk calling capability |
| **KEEP** | Existing auth | Adequate base for central admin APIs |
| **KEEP** | Local STT | Supports kiosk voice workflow without requiring cloud transcription |
| **SIMPLIFY** | Kiosk query error handling | Broad catch silently changes data source |
| **SIMPLIFY** | SQL ordering | Random selection prevents reproducibility |
| **SIMPLIFY** | Runtime health | Liveness currently hides dependency failure |
| **SIMPLIFY** | Configuration | Historical provider/deployment flags need evidence-based pruning |
| **SIMPLIFY** | Import lifecycle | Separate staging, approval, promotion, and runtime |
| **MERGE** | DSN handling in `db.py` and `persistence/database.py` | Duplicate URL conversion/SSL logic |
| **MERGE** | Resource query behavior | General and kiosk paths should share retrieval without sharing mock fallback |
| **MERGE** | 211/menu configuration | Multiple hardcoded definitions invite drift |
| **DELETE** | `presentation/routes.py` | Unreachable duplicate query/SMS routes |
| **DELETE** | `presentation/kiosk_routes.py` | Unreachable predecessor of `kiosk_core_routes.py` |
| **DELETE** | `presentation/sms_api.py` | Orphan standalone app; SMS router is mounted in core API |
| **DELETE** | `presentation/kiosk_call_api.py` | Orphan standalone app; call router is mounted in core API |
| **UNKNOWN** | `api/kiosk/call/index.py` | Legacy Vercel entrypoint; verify deployment before delete |
| **UNKNOWN** | Fly/Vercel/GHCR/self-hosted overlap | Need current deployment ownership evidence |
| **UNKNOWN** | HealthScout SQLite/LLM path | Measure production usage and unique data first |
| **UNKNOWN** | Bedrock support | No confirmed production need or tests |

# 8. Ranked issue register

| ID | Severity | Area | Problem | Consequence | Recommended fix |
| --- | --- | --- | --- | --- | --- |
| TB-001 | **CRITICAL** | Query integrity | Any real-query exception silently returns mock agencies | Fake/stale data appears authoritative during outages and bugs | Remove production mock fallback; explicit source and controlled failure |
| TB-002 | **CRITICAL** | Data lifecycle | Running backend truncates/reloads catalog at startup | Manual curation can be destroyed by restart/update | Deploy explicit non-mutating runtime lifecycle after rollback test |
| TB-003 | **CRITICAL** | Recovery | Repo lacks migration `003` present in Neon | Schema cannot be reproduced or safely advanced | Recover and commit exact migration before further DDL |
| TB-004 | **HIGH** | Authority | Local Pi remains runtime authority while Neon also contains full catalog | Edits diverge; multiple kiosks create multiple truths | Cut central API to Neon, then snapshots, then remove local authority |
| TB-005 | **HIGH** | Determinism | `ORDER BY RANDOM()` selects agencies/providers | Same request yields untestable and inconsistent output | Stable priority/name/ID ordering |
| TB-006 | **HIGH** | Health | `/api/health` checks process only | Dead database/vector provider can look healthy | Separate liveness and readiness |
| TB-007 | **HIGH** | Credentials | Available Neon string uses `neondb_owner` | Compromised runtime can alter schema/data | Create least-privilege pooled application role |
| TB-008 | **HIGH** | Offline behavior | Current outage fallback is mock JSON, not last-known-good catalog | Offline results are incomplete and misleading | Authenticated, checksummed SQLite snapshots |
| TB-009 | **MEDIUM** | Startup auth | `seed_admin()` runs in lifespan and swallows failures | Startup mutates DB; auth can be broken while service starts | Explicit admin bootstrap command |
| TB-010 | **MEDIUM** | Duplication | Dead routes/apps and duplicate menu/query wiring | Developers can edit the wrong path | Delete verified dead modules in isolated batch |
| TB-011 | **MEDIUM** | Persistence | Sync psycopg, async SQLAlchemy, LangChain PGVector, SQLite coexist | More connection/config failure modes | Consolidate only after central path is stable |
| TB-012 | **MEDIUM** | Schema | One category and one phone string per agency | Real organizations and intake numbers are misrepresented | Measure data; minimally normalize only where justified |
| TB-013 | **MEDIUM** | Deployment | Fly, Vercel, local Docker, GHCR runner, Tailscale overlap | Unclear ownership and stale paths | Choose Fly + Neon + kiosk Compose; retire verified obsolete paths |
| TB-014 | **LOW** | Documentation | Historical counts and `pointer-fork` references drifted | Operations use wrong commands/mental model | Keep audit and runbooks tied to verified commands |

# 9. The 20% of this codebase needed to understand 80%

| File | Purpose | Who calls it | What it calls | State owned | Simplify? |
| --- | --- | --- | --- | --- | --- |
| `app/backend/main.py` | Backend CLI and Uvicorn entry | Container/operations | Alembic, import/vector commands, API | None directly | Keep commands explicit |
| `app/backend/docker-entrypoint.sh` | Runtime process setup | Docker image | Optional Tailscale, command exec | Tailscale process/state | No DB mutation |
| `app/backend/src/presentation/core_api.py` | Active FastAPI app factory | `presentation/api.py` | All active routers, admin seed | App lifecycle | Remove startup writes |
| `app/backend/src/presentation/api.py` | Active Uvicorn app export | `main.py` | `core_api.app` | None | Keep or deliberately inline later |
| `app/backend/src/presentation/kiosk_core_routes.py` | Active kiosk config/query/STT/event endpoints | Core API | Kiosk services | Home-menu definition | Keep, reduce hardcoding |
| `app/backend/src/application/services/kiosk_query_service.py` | Kiosk query orchestration and normalization | Kiosk route | Categorizer, SQL executor, mock catalog | Cached mock data | Remove production mock behavior |
| `app/backend/src/presentation/query_runtime.py` | Active general-query dependency graph | Query routes | QueryHandler and integrations | Module singletons | Keep initially |
| `app/backend/src/application/services/query_handler.py` | General query orchestration | Query/SMS runtime | Categorizer, SQL, HealthScout | None | Align retrieval with kiosk path |
| `app/backend/src/infrastructure/vector_store/pgvector_query_categorizer.py` | Semantic category routing | Query services | Embeddings + LangChain PGVector | Collection configuration | Central only |
| `app/backend/src/infrastructure/sql_agent/sql_executor.py` | Agency SQL retrieval | Query services | PostgreSQL | None | Remove random ordering |
| `app/backend/src/infrastructure/config.py` | Environment/settings contract | Nearly all backend modules | Pydantic settings | Cached settings | Prune after deployment decision |
| `app/backend/src/infrastructure/seeds/agency_seeder.py` | Destructive CSV replacement | Explicit CLI | CSV + PostgreSQL | Replaces catalog | Import/staging only |
| `app/backend/src/infrastructure/seeds/vector_seeder.py` | Category-vector build | Explicit CLI | Embedding provider + PGVector | Category collection | Central build only |
| `app/backend/alembic/versions/001_initial.py` | Initial catalog/vector schema | Alembic | PostgreSQL DDL | Schema | Recover missing `003` |
| `app/frontend/src/hooks/useKioskStateMachine.js` | Main kiosk interaction/state flow | Kiosk page/components | Kiosk API, keypad/voice/call hooks | Browser session state | Keep; avoid backend logic here |
| `app/frontend/src/lib/kioskApi.js` | Kiosk HTTP client | State machine/hooks | Backend endpoints | None | Keep one stable local API boundary |
| `app/frontend/src/pages/KioskPage.jsx` | Main kiosk page composition | React router | Kiosk components/hooks | None | Keep |
| `app/docker-compose.yml` | Current three-service appliance | Root Compose/systemd/operator | Postgres/backend/frontend | Named-volume topology | Remove local Postgres later |
| `talkbox` | Operator update/restart/status/doctor interface | Human/systemd | Git, Compose, Twilio, Chromium | Deployment state | Keep as appliance control plane |
| `kiosk-setup.sh` | Pi boot/browser/audio/system setup | Human installer | systemd, X/Openbox, udev | Device configuration outside git | Keep; document generated files |

## Suggested reading order

1. `app/docker-compose.yml`
2. `app/backend/docker-entrypoint.sh`
3. `app/backend/main.py`
4. `app/backend/src/presentation/core_api.py`
5. `app/backend/src/presentation/kiosk_core_routes.py`
6. `app/frontend/src/lib/kioskApi.js`
7. `app/frontend/src/hooks/useKioskStateMachine.js`
8. `app/backend/src/application/services/kiosk_query_service.py`
9. `app/backend/src/infrastructure/vector_store/pgvector_query_categorizer.py`
10. `app/backend/src/infrastructure/sql_agent/sql_executor.py`
11. `app/backend/src/infrastructure/config.py`
12. `app/backend/src/infrastructure/seeds/agency_seeder.py`
13. `app/backend/src/infrastructure/seeds/vector_seeder.py`
14. `app/backend/alembic/versions/001_initial.py`
15. `talkbox`
16. `install.sh`
17. `kiosk-setup.sh`

# 10. Minimum production architecture

## Recommended services

- React frontend
- one central FastAPI backend on Fly
- one canonical Neon PostgreSQL database with pgvector
- Twilio for voice/SMS functions that are confirmed necessary
- local whisper.cpp on kiosks while it remains operationally useful
- one read-only SQLite catalog snapshot per kiosk for outages

Do not add Kubernetes, Redis, queues, GraphQL, microservices, another auth provider, or local vector inference.

## Online path

```text
Kiosk browser -> local kiosk backend/proxy -> Fly FastAPI -> Neon
```

Keeping the local backend as the browser's stable boundary avoids embedding central credentials in React and gives one place to apply bounded network timeout and snapshot fallback.

## Offline path

```text
Fly snapshot publisher
  -> authenticated HTTPS manifest
  -> version comparison
  -> streamed temporary download
  -> size + SHA-256 + SQLite integrity/schema validation
  -> fsync
  -> atomic rename
  -> deterministic local SQLite query
```

The snapshot contains facts and retrieval aids, not vectors or secrets. Offline intent resolution should use simple category/FTS matching and stable ordering. If intent is uncertain, offer 211 instead of guessing.

# 11. Neon and Fly setup recommendation

Neon target:

- organization `org-super-sunset-88688178`
- project `soft-hat-27629835`
- database `neondb`

Current Neon is populated and matches local data, but setup is incomplete for production runtime.

## Required next steps

1. Recover migration `003_resource_import_staging` into version control.
2. Create a protected/rehearsal Neon branch.
3. Create separate roles:
   - migrator: direct connection, DDL only when explicitly used
   - importer: direct connection, controlled staging/import permissions
   - application: pooled connection, least-privilege runtime access
4. Remove owner credentials from future Fly runtime configuration.
5. Use the direct endpoint for Alembic and deliberate imports.
6. Use the pooled endpoint for Fly runtime.
7. Require SSL and verify driver behavior for both sync and async clients.
8. Build agency vectors into a fresh, versioned collection separate from `query_categories`.
9. Record embedding provider, model, dimensions, agency ID, category, and content hash.
10. Validate row counts, duplicates, phone quality, vector counts/dimensions, and semantic fixtures.
11. Create a Neon restore point/branch and rehearse recovery.
12. Deploy Fly with all migration/import/vector/admin bootstrap behavior disabled at runtime.
13. Validate Twilio webhooks, liveness, readiness, auth, connection limits, and query provenance.

The Neon Console Tables view is appropriate for developer inspection and emergency correction, but ordinary staff should not be made Neon administrators.

# 12. Minimal nontechnical editing design

This audit does not implement a new feature. The recommended later interface is `/admin/resources`, backed by central authenticated CRUD endpoints and existing auth.

Minimum workflow:

- search and filter resources
- view details and provenance
- add a resource
- edit facts
- disable instead of hard-delete
- mark verified
- show last verified/updated timestamps

Likely minimum fields:

- name
- phone
- address
- website
- description
- category/categories
- status (`active`, `inactive`, `unverified`)
- source and source URL
- last verified at
- updated at

Write operations belong in FastAPI. The browser never receives database credentials. Imports enter staging and require review before canonical promotion.

# 13. Data-model review

## One category per agency

Current `agencies.category_id` allows one category. Real organizations often provide shelter, food, case management, medical care, and veteran services simultaneously. The CSV also repeats some organizations across categories, which may be compensating for this limitation.

A future `agency_categories` join table would improve correctness and reduce duplication, but it affects queries, imports, admin editing, snapshots, and vectors. Do not include it in the first cutover. First measure duplicate organizations and multi-service records; then migrate with compatibility views or dual-read tests.

## Phone numbers

A single free-form phone string is insufficient for:

- main versus intake numbers
- youth/adult lines
- extensions
- multiple locations
- numbers embedded in descriptions
- dial safety/normalization

Because calling is core, the minimum later normalization should distinguish a dialable normalized number, display value, purpose, extension, and active status. Do not build a general contact-management subsystem before measuring the actual exceptions.

# 14. Observability requirements

Separate:

- liveness: process can answer HTTP
- readiness: required production dependencies are usable

A non-secret readiness/admin diagnostic should report:

- backend version/commit
- database host class and database name, never credentials
- connectivity and query latency
- canonical catalog version and row count
- active category and agency vector collection names
- embedding model identity/dimensions
- snapshot version and last successful sync on kiosks
- mock runtime disabled
- last successful query source
- Twilio configuration alignment without tokens

Log structured events for central query failure, snapshot fallback, snapshot sync/checksum failure, and import promotion. Do not log user secrets or full connection strings.

# 15. Pi safety and rollback checklist

## Boot sequence to preserve

Depending on installed OS/session mode:

1. Docker starts.
2. `talkbox-stack.service` starts the root Compose project.
3. tty1 auto-login/startx or desktop autostart begins the kiosk session.
4. Openbox/X settings disable blanking and expose maintenance hotkeys.
5. `/usr/local/bin/talkbox-kiosk-browser` waits for backend health and launches Chromium.
6. Chromium opens `http://localhost:8084/kiosk`.
7. Audio initialization and WirePlumber policy select Tonor input and MV-SILICON P10S output.

## Device-specific state to preserve

- `app/.env` and future scoped kiosk credentials
- `~/.config/wireplumber/wireplumber.conf.d/90-talkbox-audio.conf`
- `/etc/asound.conf` if generated by kiosk setup
- `/usr/local/bin/talkbox-*`
- `/etc/systemd/system/talkbox-*.service`
- tty/autologin and X/Openbox/autostart files
- Tailscale state/configuration
- Twilio public URL and application alignment
- Docker named volumes until final local-Postgres retirement
- local STT model files

## Software rollback

1. Record `git rev-parse HEAD`, image IDs, `docker compose -p talkbox config`, and `docker compose -p talkbox ps` before deployment.
2. Preserve `app/.env` outside any checkout operation.
3. Ensure the working tree is committed or otherwise preserved before switching revisions.
4. Return to the known-good revision or image tag.
5. Run `docker compose -p talkbox build` and `docker compose -p talkbox up -d` from repository root as required.
6. Do not pass `-v` and do not delete named volumes.
7. Verify backend/frontend health, then hard-reload Chromium without killing its launcher.

## Database rollback

- Local: restore only from the validated custom-format dump into a controlled target after preserving the damaged database.
- Neon: use a protected branch/restore point first; compare counts and deterministic export hashes before reopening writes.
- Never use destructive CSV replacement as a rollback mechanism for curated production data.

## Appliance acceptance checklist

- Tonor is default input
- P10S is default output; P10S microphone does not win default source
- keypad buttons and tones work
- typed and spoken query work
- 211 remains reachable during API failure
- Twilio call setup, audio in both directions, hangup, and idle handling work
- screen dim/wake works
- Chromium reload/restart behavior works
- online query reports central provenance
- offline query reports snapshot provenance/version
- snapshot corruption/interruption preserves the prior copy

# 16. Deployment simplification

Preferred production ownership:

| Concern | Target |
| --- | --- |
| Frontend/kiosk UI | Built image served locally on each Pi, or central static hosting only if outage UX remains available |
| Central API and Twilio webhooks | Fly FastAPI |
| Canonical facts and vectors | Neon |
| Offline catalog | Read-only SQLite in kiosk `/data` volume |
| Image distribution | GHCR if current pipeline is verified; otherwise simplify to one build path |
| Remote device access | Tailscale only if still needed after Fly webhook cutover |
| Vercel backend functions | Delete after usage confirmation |
| Local Pi PostgreSQL | Remove after central + snapshot soak test |

The final kiosk Compose stack should not contain PostgreSQL or embedding dependencies. It should contain only what the kiosk needs to display UI, call the central API, perform local STT/calling integration, and query its last-known-good snapshot.

# 17. What I would delete

| File/component | Reason | Evidence | Risk | Verification before deletion |
| --- | --- | --- | --- | --- |
| `src/presentation/routes.py` | Duplicate inactive routes/object graph | Not mounted by `core_api.py`; active routes live elsewhere | Low | Import search, route inventory, API smoke tests |
| `src/presentation/kiosk_routes.py` | Inactive predecessor | `core_api.py` mounts `kiosk_core_routes.py` | Low | Import search and kiosk endpoint tests |
| `src/presentation/sms_api.py` | Orphan standalone FastAPI app | Core app directly mounts SMS router | Low | Confirm no external module target uses it |
| `src/presentation/kiosk_call_api.py` | Orphan standalone FastAPI app | Core app directly mounts call router | Low | Confirm no external module target uses it |
| Production mock fallback logic | Hides real failures | Broad exception path returns fixture | High behavioral change | Forced DB/vector/provider failure tests |
| `kiosk_mock_catalog.json` | Duplicate partial catalog | Used by production fallback | Medium | Move explicit test data first, verify `/demo` ownership |
| `api/kiosk/call/index.py` | Legacy Vercel compatibility path | Separate active core API exists | Medium | Confirm Vercel deployment history/DNS |
| Local Postgres service on Pi | Makes appliance a database authority | Current Compose and volume | High until snapshot proven | Central and offline soak test, rollback image |
| HealthScout SQLite path | Parallel data/query system | Separate DB and LLM extraction | High/unknown | Usage telemetry and unique-data comparison |
| Bedrock branch | Provider complexity without confirmed use | Config/factory support, no confirmed deployment | Medium | Environment/deployment/test evidence |
| Stale Fly/Vercel/runner files | Multiple deployment stories | Historical configs coexist | Medium | Name current owner and last deployment for each |

Do **not** delete `app/backend/src/presentation/api.py` in the first batch. `main.py` currently points Uvicorn at `src.presentation.api:app`.

# 18. Direct answers to the 16 operating questions

1. **Where does every TalkBox get resource data?** Today this Pi queries local Postgres and may silently fall back to mock JSON. The target is Fly API to Neon, with a read-only local snapshot during outages.
2. **What is the single source of truth?** There is not one operationally today. Neon is populated and intended to become the sole authority after cutover.
3. **Why am I seeing mock-catalog resources?** Either `KIOSK_MOCK_QUERY=true` or any exception occurred in embedding/vector/database/query code.
4. **Can a broken database silently look healthy?** Yes. `/api/health` checks process liveness, and kiosk query failures can return mock success.
5. **Can restarting a kiosk overwrite curated data?** Yes in the running image. The `dev` safety change exists but is not deployed.
6. **Where does the production database live today?** The serving kiosk uses `talkbox-postgres` on the Pi. Neon has an exact copy but is not yet serving that kiosk.
7. **Is Neon used or only supported historically?** It is real, migrated, and populated, but not yet the runtime authority.
8. **How can I inspect canonical data visually?** Today via local Postgres tools; after cutover, Neon Console Tables for technical owners. Staff should use the future admin UI.
9. **How can nontechnical staff edit safely?** They cannot yet. The target is authenticated `/admin/resources` with disable/verify rather than hard delete.
10. **How is a new TalkBox added without another database?** Provision the kiosk with scoped central/snapshot credentials; it calls Fly/Neon and downloads a snapshot. It does not create Postgres.
11. **How is software updated without affecting data?** Runtime startup must be non-mutating; canonical data stays in Neon and snapshots stay in a persistent volume.
12. **How do I recover from failed deployment?** Return to recorded commit/image/config, preserve `.env` and volumes, recreate services without `-v`, then run appliance checks.
13. **How do I recover accidental data changes?** Neon protected branch/restore point or validated dump; compare counts/hashes before reopening writes.
14. **Which files explain most of the system?** The files and reading order in section 9.
15. **What can be deleted?** Verified inactive presentation modules first; mock runtime, local Postgres, HealthScout, provider and deployment paths only after their replacements/usage are proven.
16. **What is the smallest reliable architecture?** React kiosk, one FastAPI service on Fly, Neon Postgres/pgvector, Twilio, local STT as needed, and a read-only SQLite outage snapshot.

# Immediate review decisions

Before implementation resumes, the development team should approve these points:

1. Neon is canonical only after Fly cutover, despite already containing matching data.
2. Offline support is a read-only SQLite snapshot, not local Postgres and not local vectors.
3. Migration `003_resource_import_staging` must be recovered before further DDL.
4. The four verified orphan modules may be deleted in one isolated batch; `presentation/api.py` stays.
5. Mock fallback and random ordering are removed before central cutover.
6. Owner credentials are never used by Fly or kiosks.
7. Local Postgres remains untouched until one kiosk passes central and outage soak tests.

# Recommended change sequence

## Phase 0 - Preserve the Pi and finish the evidence baseline

**Goal:** Make every later change reversible.

**Likely files:** documentation only; device state outside repo.

**Risk:** Low.

**Test:** Validate dump archive, record commit/images/config, complete appliance checklist.

**Rollback:** Not applicable; read-only.

**Done when:** A developer unfamiliar with the Pi can restore software, config, database, audio, browser, and Twilio behavior.

## Phase 1 - Recover migration history and deploy non-mutating startup

**Goal:** Make schema reproducible and stop restart-time catalog replacement.

**Likely files:** `alembic/versions/003_*.py`, `docker-entrypoint.sh`, `main.py`, `install.sh`, startup docs.

**Risk:** High because current Pi relies on old startup behavior.

**Test:** Disposable DB from migrations; repeated restart preserves counts and a deliberate edit; isolated backend image and API smoke tests.

**Rollback:** Revert one deployment commit/image; preserve local DB volume.

**Done when:** Repo migrates an empty DB to Neon-equivalent schema and ordinary restart performs zero catalog writes.

## Phase 2 - Remove silent mock fallback and randomness

**Goal:** Make results truthful and deterministic.

**Likely files:** `kiosk_query_service.py`, `sql_executor.py`, HealthScout query, response schemas/tests.

**Risk:** Medium; outages become visible instead of appearing successful.

**Test:** Force DB, provider, and vector failures; assert no fixture agencies. Repeat unchanged queries and assert stable order.

**Rollback:** Revert application commit; do not restore mock behavior silently in production.

**Done when:** Every response identifies real source/version and unchanged input/data produces stable results.

## Phase 3 - Add readiness and provenance

**Goal:** Distinguish live process from healthy production dependencies.

**Likely files:** query routes, schemas, database/vector diagnostics, logging.

**Risk:** Low to medium if orchestrator health checks are changed too quickly.

**Test:** Liveness survives dependency outage; readiness fails with a specific non-secret reason.

**Rollback:** Keep liveness endpoint stable; revert readiness consumers separately.

**Done when:** Operators can prove database identity, catalog count/version, vector collection, and last query source.

## Phase 4 - Establish least-privilege Neon/Fly central service

**Goal:** Make Neon the sole writable authority and Fly the production API.

**Likely files:** Fly config, settings/DSN handling, secrets/runbooks, CI deployment.

**Risk:** High; central connectivity and Twilio webhooks become production dependencies.

**Test:** Rehearsal branch, role grants, pooled/direct connections, counts/hashes, semantic fixtures, auth, Twilio, connection limits, restore rehearsal.

**Rollback:** Point Fly to protected prior branch/database; keep kiosk local path unchanged during soak.

**Done when:** Fly serves verified central queries using a non-owner role and no startup mutations.

## Phase 5 - Publish authenticated catalog snapshots

**Goal:** Produce deterministic, validated offline artifacts from canonical Neon data.

**Likely files:** central catalog service/routes, SQLite exporter, manifest schema, tests.

**Risk:** Medium; a bad artifact could poison offline results.

**Test:** Transactional export, reproducibility, checksum, size, schema version, `integrity_check`, authentication, failed-publication behavior.

**Rollback:** Retain previous published version and disable new manifest.

**Done when:** Invalid generation never replaces the last good snapshot.

## Phase 6 - Add kiosk last-known-good fallback

**Goal:** Keep useful resource search during T-Mobile outages without fake data.

**Likely files:** local backend client/fallback service, sync command/service, Compose volume/config, tests.

**Risk:** High on appliance behavior.

**Test:** Boot offline, DNS failure, timeout, corrupt/truncated download, disk full, schema mismatch, atomic replacement, online recovery, provenance.

**Rollback:** Disable fallback/sync and restore prior kiosk image/config; local Postgres remains available during pilot.

**Done when:** One pilot Pi passes online/offline soak testing and 211/calling remain available.

## Phase 7 - Remove local resource authority

**Goal:** Make kiosks replaceable appliances.

**Likely files:** kiosk Compose, backend dependencies/image, installer, update/doctor commands.

**Risk:** High; removal is irreversible without preserved image/volume.

**Test:** Reboot, rebuild, update, and provision second kiosk without import/vector generation; verify no Neon write privilege.

**Rollback:** Restore previous Compose/image and retained Postgres volume during rollback window.

**Done when:** No kiosk runs PostgreSQL, canonical imports, or embedding jobs.

## Phase 8 - Add minimal controlled editing

**Goal:** Let authorized nontechnical staff maintain canonical resources safely.

**Likely files:** central CRUD routes/services/schemas, existing auth permissions, React admin page.

**Risk:** High to data quality; this is feature work and follows simplification.

**Test:** Authorization, validation, audit fields, disable/verify flow, concurrent edits, snapshot/version update, no browser DB credentials.

**Rollback:** Disable write routes/UI; restore Neon branch for bad data.

**Done when:** Routine edits require neither Neon admin access nor SSH.

## Phase 9 - Delete obsolete paths and review schema limits

**Goal:** Reduce total concepts after production evidence exists.

**Likely files:** dead presentation modules, mock files, Vercel/Fly remnants, HealthScout/Bedrock paths, DSN helpers, schema migrations if justified.

**Risk:** Varies by deletion batch.

**Test:** One small deletion per commit with import, route, build, deployment, and appliance checks.

**Rollback:** Revert the individual deletion commit.

**Done when:** One obvious query path, one deployment story, one authority, and no unverified compatibility code remain.

