# Local Agent Handoff: Replit Resources and Lightweight SQLite TalkBox

> Archived and superseded. The standalone TalkBox Neon project is canonical;
> FSC synchronization is disabled. Do not implement this handoff unless an
> explicit architecture decision restores the former FSC model.

## Mission

Simplify TalkBox so that:

1. The FSC Resource Platform on Replit is the only canonical editor and source
   of truth for public community resources.
2. TalkBox consumes those resources through the authenticated, versioned Replit
   API. Do not connect kiosks or ordinary Fly runtime code directly to Neon.
3. The local Docker stack no longer needs a PostgreSQL/pgvector container.
4. Small local state and the last-known-good public resource snapshot are stored
  in SQLite and work on client appliances across Raspberry Pi, Linux, and
  macOS Docker Desktop. The design must not depend on Raspberry Pi hardware.
5. The production kiosk interface, routes, keypad behavior, and Twilio calling
   experience do not visually change.

This is an implementation task, not an architecture-only review. Work in small,
tested phases and leave a rollback path after every phase.

## Non-Negotiable Boundaries

- Synchronize public resource/configuration data only.
- Never synchronize users, clients, participants, submissions, case data,
  authentication records, audit records, or kiosk interaction events.
- Never place `REPLIT_DB`, a Neon connection string, `FSC_RESOURCE_API_KEY`, or
  `FLY_RESOURCE_API_KEY` in the browser or on a remote kiosk client.
- Do not make Neon schema details the TalkBox integration contract. The Replit
  `/api/v1/talkbox/*` API is the contract.
- A resource phone number is callable only when an active upstream contact has
  `allow_talkbox_call=true` (currently accepted as `allow_call` by TalkBox).
- Preserve the fixed 211 behavior unless a tested replacement is explicitly
  approved. Never weaken server-side call authorization.
- Do not modify FSC production resource records during tests.
- Do not delete the existing PostgreSQL volume until migration, rollback, and
  soak checks pass.
- Do not change the frontend design. The boot intro popup was intentionally
  removed from `app/frontend/src/components/kiosk/KioskShell.jsx`.

## Verified State as of 2026-07-25

### Replit and Neon

- Published Replit origin is configured locally as `REPLIT_ORIGIN_URL`.
- `GET /api/health` returns 200.
- `GET /api/ready` returns 200.
- Authenticated `GET /api/v1/talkbox/version` returns 200.
- Authenticated `GET /api/v1/talkbox/bootstrap` returns 200.
- Invalid bearer credentials return 401.
- The live bootstrap validates with the current Pydantic models.
- The canonical Neon database has 394 published resources, 39 active
  categories, and 3 announcements.
- The API currently publishes zero TalkBox services because the
  `service_distribution` table has zero rows. Its channel enum includes
  `TALKBOX`. This must be resolved through the FSC Staff CMS/publication flow,
  not by TalkBox writing directly to Neon.
- There are currently zero active contacts approved for TalkBox calling.

### Fly

- Existing app: `talkbox`; do not create a second app.
- Primary region: `lax`.
- One Machine is kept running because Twilio/Tailscale behavior depends on it.
- `/healthz`, `/readyz`, `/api/health`, and `/api/kiosk/sync-status` are live.
- Fly has `FLY_RESOURCE_API_KEY` as a secret.
- Fly has the verified Replit origin configured under
  `FSC_RESOURCE_API_BASE_URL`.
- Current code accepts both canonical names and compatibility names:
  - `FSC_RESOURCE_API_BASE_URL` or `REPLIT_ORIGIN_URL`
  - `FSC_RESOURCE_API_KEY` or `FLY_RESOURCE_API_KEY`
- Production currently reports `upstream_configured=true`, no cache, and a
  `ValueError`, because the zero-service bootstrap is deliberately rejected.
- Existing kiosk resource queries continue to use the legacy fallback and were
  verified to return results.

### Current Safety Guard

`ResourceSyncService.refresh()` rejects a bootstrap containing zero services.
Do not remove this guard until the upstream contract provides an explicit,
trusted signal that an intentionally empty catalog is valid. A malformed or
empty update must never erase a working last-known-good snapshot.

### Worktree

Inspect `git status` before editing. At handoff time there may be uncommitted
changes in:

- `app/backend/src/infrastructure/config.py`
- `app/backend/src/application/services/resource_sync_service.py`
- `app/backend/tests/test_resource_sync_service.py`
- `app/frontend/src/components/kiosk/KioskShell.jsx`

Treat them as intentional user/previous-agent work. Do not revert them.

## Target Architecture

```text
FSC staff
   |
   v
FSC Staff CMS on Replit
   |
   v
Canonical Neon PostgreSQL
   |
   v
Authenticated /api/v1/talkbox/* API
   |
   v
TalkBox FastAPI on Fly
   |  validates + atomically caches public snapshot
   v
TalkBox kiosk API
   |
   v
Local SQLite last-known-good cache
```

The local SQLite database is a disposable cache/state store, not a second
editable resource directory.

## Actual Website and Backend Wiring

The same frontend and backend source currently serve several deployment roles.
Do not treat them as one runtime when changing credentials or persistence:

```text
Client appliance browser
  -> local nginx/frontend container
  -> local talkbox-backend container for /api/*

Vercel-hosted frontend
  -> vercel.json rewrite
  -> https://talkbox.fly.dev/api/*

CI-built frontend image
  -> build-time VITE_API_URL
  -> configured backend, which may be Fly or a Compose backend
```

The appliance nginx configuration always proxies `/api/*` to its local backend
container. The kiosk browser therefore does not call Fly directly. The client
backend must eventually download a public snapshot from Fly using a distinct,
revocable, read-only client credential and then answer the browser from its
local SQLite snapshot during an outage.

Only the central Fly role may hold `FSC_RESOURCE_API_KEY` and call Replit.
The central Fly cache and each client offline snapshot are separate SQLite files
with separate lifecycles. A Fly cache protects Fly from a Replit outage or
process restart; a client snapshot protects the kiosk from a Fly or network outage.

## Environment File Contract

Consolidate configuration around two clearly separated files.

### `app/.env`: local application runtime

This is the only env file loaded into local Docker services. On a client appliance,
it must not contain the FSC service credential or a Neon connection string.
The snapshot client may use a separately scoped Fly credential:

```dotenv
LOCAL_STATE_DATABASE_URL=sqlite+aiosqlite:////data/talkbox.sqlite3
FSC_RESOURCE_CACHE_PATH=/data/resource-snapshot.sqlite3
TALKBOX_CENTRAL_API_BASE_URL=https://talkbox.fly.dev
TALKBOX_CLIENT_SNAPSHOT_KEY=<scoped-read-only-client-key>
```

For central Fly deployment, configure `FSC_RESOURCE_API_BASE_URL` and
`FSC_RESOURCE_API_KEY` as Fly secrets rather than copying an env file. Configure
`TALKBOX_SNAPSHOT_PUBLISH_KEYS` separately as the comma-separated client keys
accepted by the Fly snapshot endpoint; do not reuse the FSC service key.

Retain existing Twilio, OpenAI, cookie, kiosk, and local runtime settings that
are still required. Never commit this file.

### Root `.env.local`: operator/deployment tooling only

This file is never loaded into application containers. It may contain operator
credentials such as:

```dotenv
FLY_TOKEN=<operator-token>
REPLIT_DB=<diagnostic-only-direct-connection-if-still-needed>
```

After configuring the canonical resource origin and bearer key as Fly secrets,
remove duplicate runtime copies from root `.env.local`. Do not print values
while moving them. Do not pass `FLY_TOKEN`, the FSC service key, or direct Neon
credentials into client Docker services.

Update `app/.env.example`, README, scripts, and Compose so this ownership is
obvious. Examples must contain no real secrets. Prefer canonical `FSC_*` names;
retain compatibility aliases for one deprecation cycle.

## Why PostgreSQL Cannot Be Removed in One Blind Edit

The current PostgreSQL container serves multiple concerns:

1. Legacy `agencies` and `categories` resource queries.
2. pgvector query categorization.
3. FastAPI Users authentication in `users`.
4. Legacy TalkBox admin CRUD/import staging.
5. Call allowlisting through the legacy `agencies` table.

Relevant ownership points include:

- `app/backend/src/infrastructure/database.py`
- `app/backend/src/infrastructure/persistence/database.py`
- `app/backend/src/infrastructure/vector_store/pgvector_query_categorizer.py`
- `app/backend/src/infrastructure/sql_agent/sql_executor.py`
- `app/backend/src/presentation/admin_routes.py`
- `app/backend/src/application/services/kiosk_call_service.py`
- `app/backend/src/presentation/query_runtime.py`
- `app/docker-compose.yml`

Replace or retire each consumer before removing `talkbox-postgres`.

## Implementation Phases

### Phase 1: Finish the Replit Publication Path

1. Confirm FSC Staff CMS can assign published resources to channel `TALKBOX`.
2. Publish a small representative set first through the CMS.
3. Confirm `content_version` changes.
4. Confirm `/api/v1/talkbox/services` and `/bootstrap` return nonzero services.
5. Confirm only public fields are present and only explicitly approved active
   contacts become callable.
6. Let Fly synchronize automatically; verify `/api/kiosk/sync-status` has a
   version and `/api/kiosk/resources` returns the validated snapshot.
7. Verify existing kiosk response shapes remain unchanged.

Do not proceed to deleting local resource infrastructure while upstream still
publishes zero services.

### Phase 2: Implement Persistent SQLite Last-Known-Good Cache

First persist Fly's validated cache in a tiny SQLite repository while retaining
an in-memory snapshot for fast reads. This does not by itself provide client
outage support; add authenticated Fly publication and a separate client snapshot
installer before removing the appliance's legacy database.

Suggested table:

```sql
CREATE TABLE resource_snapshot (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    schema_version TEXT NOT NULL,
    content_version TEXT NOT NULL,
    generated_at TEXT,
    fetched_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
```

Requirements:

- Use Python `sqlite3` or SQLAlchemy/aiosqlite; do not add a server process.
- Store the validated public bootstrap JSON only.
- Validate cached JSON with `BootstrapSnapshot` when loading it.
- Write in one transaction and atomically replace the singleton row.
- Load SQLite first at startup, then refresh from Replit.
- Never replace a valid row with malformed, unauthorized, timed-out, or empty
  content.
- Keep serving the last-known-good row during Replit or Fly outages.
- Use a Docker volume mounted at `/data`; do not depend on container rootfs.
- Add corruption recovery that preserves the bad file for diagnosis rather
  than silently deleting it.
- Never put users, clients, events, submissions, audit data, or API keys in the
  snapshot database.

Add tests for restart persistence, atomic replacement, corruption, schema
validation, timeout, unauthorized response, unchanged version, concurrent
refresh, and empty catalog rejection.

### Phase 3: Move Every Resource Read to the Canonical Snapshot

Make both kiosk and desktop query paths read the synchronized snapshot. Remove
their dependency on local `agencies`, `categories`, and pgvector.

The existing lexical ranking in `ResourceSyncService.query()` is acceptable as
an initial deterministic replacement, but improve it only with focused tests.
Do not add another editable local catalog. If semantic search is still required,
use an in-process/on-disk index derived from the snapshot, not canonical data.

Requirements:

- Deterministic ordering; no `ORDER BY RANDOM()`.
- Return the existing frontend response models.
- Include enough provenance in logs/status to prove whether results came from
  Replit cache or an emergency fallback.
- Do not silently show mock data after a production query exception.
- Emergency 211 fallback may remain clearly identified.
- API-approved callable status must flow to the UI, while the backend repeats
  authorization at call time.

### Phase 4: Retire Local Resource Editing

The FSC Staff CMS is the editing interface. TalkBox admin resource writes must
not create a second authority.

Choose the smallest compatible option after inspecting actual use:

- remove unused TalkBox resource admin routes/components, or
- make them read-only and point operational users to FSC Staff CMS, or
- proxy explicitly supported operations to the FSC API if that contract exists.

Do not write directly to Neon. Preserve unrelated authentication and partner
console behavior unless its removal is explicitly approved.

### Phase 5: Convert Remaining Local State to SQLite

After resource and pgvector consumers are gone, convert remaining required
FastAPI Users/local state from PostgreSQL to SQLite.

Recommended URL:

```text
sqlite+aiosqlite:////data/talkbox.sqlite3
```

Requirements:

- Add `aiosqlite` explicitly.
- Make SQLAlchemy engine setup backend-neutral.
- Use SQLite-compatible UUID/date defaults and migrations/schema initialization.
- Preserve existing admin authentication where it is still used.
- Migrate required user records deliberately or document a controlled admin
  recreation path. Never copy FSC participants or clients.
- Remove synchronous psycopg access from runtime code.
- Remove `psycopg`, `psycopg2`, `asyncpg`, `pgvector`, and
  `langchain-postgres` only after reference and import scans are clean.
- Remove PostgreSQL-only Alembic operations or create a clean SQLite baseline.
- Keep historical migrations only if clearly marked as archival and excluded
  from fresh SQLite setup.

### Phase 6: Remove PostgreSQL from Docker

Only after all previous phases pass:

- Remove `talkbox-postgres` from `app/docker-compose.yml`.
- Remove its health dependency from `talkbox-backend`.
- Remove `POSTGRES_*` and legacy `DB_URI` settings from runtime examples.
- Replace the Postgres volume with a small backend state volume at `/data`.
- Update `install.sh`, `talkbox`, kiosk setup, backup, update, and rollback
  commands.
- Do not delete the existing `talkbox-postgres-data` volume automatically.
  Document a later manual cleanup command after the rollback window.

## Platform Verification Matrix

### Linux/Raspberry Pi

- `docker compose up -d --build` starts frontend and backend with no Postgres.
- Existing `/`, `/kiosk`, `/demo`, `/chat`, and call routes retain behavior.
- Reboot loads the SQLite snapshot before attempting network refresh.
- Network loss still shows last-known-good resources.
- Twilio allowlisting remains enforced server-side.

### macOS

- Docker Desktop can build both images on Apple Silicon and Intel where
  supported.
- `docker compose up -d --build` requires no host PostgreSQL installation.
- SQLite data persists across container recreation.
- Document localhost URLs and a one-command reset of disposable local state.
- Avoid Linux-host-only assumptions in normal development paths.

### Fly

- Deploy only the existing `talkbox` app.
- Keep existing region, always-on Machine strategy, Twilio/Tailscale settings,
  and `/healthz` liveness check.
- `/healthz` must not depend on Replit availability.
- `/readyz` and sync status must describe cache availability accurately.
- Verify one running healthy Machine after every deploy.

## Required Tests

- Live Replit health, ready, version, services, and bootstrap smoke tests using
  read-only GET requests.
- Published bootstrap validates against local models.
- Client/private fields are ignored and never serialized downstream.
- Empty/malformed/newer bootstrap does not replace good SQLite content.
- Same version avoids unnecessary bootstrap download.
- Restart restores the exact last-known-good version from SQLite.
- Only active `allow_talkbox_call=true` contacts are callable.
- Existing call token/TwiML behavior still works without placing a real call in
  automated tests.
- Kiosk query response shape remains unchanged.
- Full backend tests and Ruff pass.
- Frontend production build passes.
- Compose starts without a PostgreSQL image.
- macOS and Pi instructions are accurate.

## Rollback

Before removing PostgreSQL:

1. Record current image IDs and Compose configuration.
2. Back up the existing Postgres volume without printing credentials.
3. Keep the old Compose file or a tagged release available.
4. Test rollback on a non-production machine.
5. Retain the volume through an agreed soak window.

If Replit synchronization fails, keep serving validated SQLite content. If the
SQLite cache is unavailable, use the existing legacy resource path only during
the migration window and report that provenance. Do not silently substitute
mock/demo resources in production.

## Definition of Done

- FSC staff edit and distribute resources entirely through FSC Staff CMS.
- A CMS change updates Replit/Neon, increments `content_version`, reaches Fly,
  and reaches a kiosk without code changes, SSH, Git pulls, or reimaging.
- TalkBox never synchronizes client/private data.
- No kiosk or browser has Neon credentials or the service API key.
- TalkBox starts and remains useful during a temporary upstream outage.
- The local stack has no PostgreSQL container or pgvector dependency.
- SQLite is a validated last-known-good cache/local state store, not an editable
  resource authority.
- The stack builds and runs on macOS Docker Desktop and Raspberry Pi.
- Existing kiosk UI and Twilio call behavior remain unchanged.
- Documentation identifies one obvious env file for runtime and one for
  operator tooling.

## Final Report Expected from the Implementing Agent

Report:

1. Files changed and architecture removed.
2. Final environment variable ownership and migration steps.
3. Replit API and publication verification, including service count and version.
4. SQLite schema, location, persistence, and corruption behavior.
5. Every former PostgreSQL consumer and its replacement or retirement.
6. Test/build/Compose results on available platforms.
7. Fly deployment and health status if deployed.
8. Exact remaining manual CMS actions, if any.
9. Rollback procedure and retained artifacts/volumes.

Do not claim end-to-end completion while the Replit API publishes zero services.