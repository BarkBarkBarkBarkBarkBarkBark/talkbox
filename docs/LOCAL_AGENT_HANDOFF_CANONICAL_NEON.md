# Local Agent Handoff: Canonical Neon, Admin, and Multi-Category Catalog

Use this file as the working brief for an agent running **inside a TalkBox
checkout** (local appliance, Raspberry Pi, or this repo). It supersedes
[`LOCAL_AGENT_HANDOFF_REPLIT_SQLITE.md`](LOCAL_AGENT_HANDOFF_REPLIT_SQLITE.md).
Do not implement the archived FSC/Replit/SQLite plan.

## Mission

Keep TalkBox aligned with the architecture that is already live on Fly and
Vercel:

```text
authenticated /admin on www.talk-box.org
  -> Fly FastAPI (talkbox.fly.dev)
  -> canonical TalkBox Neon project `talkbox`
  -> kiosk Browse + voice search via FastAPI
```

The local agent’s job is to make **this checkout and any local Postgres** match
that contract. Do not rebuild the product, do not invent a second resource
authority, and do not put Neon credentials in a browser or kiosk `.env`.

## Non-negotiable boundaries

- FastAPI is the only process that may hold `DB_URI`. Browsers and kiosks call
  `/api/*` only.
- Do not enable `FSC_RESOURCE_SYNC_ENABLED`. That code is dormant rollback.
- Do not run migrations, seeds, truncates, imports, or admin creation at
  application startup. `TALKBOX_SEED_ADMIN` must stay `false` unless an
  operator explicitly requests a one-shot bootstrap.
- Do not drop `agencies.category_id`. It is a denormalized primary category
  kept in sync with the first selected join-table category.
- Do not deduplicate the ~17 agencies that still exist as multiple rows. That
  is a later, separate migration.
- Do not change `query_categories` pgvector documents. Voice routing still
  maps spoken text → one category name; SQL then finds agencies.
- Do not implement [`LOCAL_FIRST_KIOSK_SYNC.md`](LOCAL_FIRST_KIOSK_SYNC.md)
  unless the user explicitly asks. Website edits currently reach kiosks that
  query Fly/Neon; local-copy sync is design-only.
- Do not change kiosk routes: production kiosk stays at `/kiosk` (and
  localhost `/`). Do not move `/chat` to `/`.

## Verified production state (2026-08-11)

| Surface | State |
| --- | --- |
| Canonical DB | Standalone Neon project `talkbox` |
| Fly | `talkbox.fly.dev`, one always-on Machine in `lax` |
| Vercel | `www.talk-box.org` project `talkbox` |
| Agencies | 379 rows |
| Categories | 29 rows |
| `agency_categories` backfill | 379 assignments, 0 agencies missing a join row |
| Alembic head | `005_agency_categories` |
| Browse visibility | `agencies.show_on_kiosk` (default true) |
| Voice search | joins `agency_categories`; does **not** filter `show_on_kiosk` |
| Admin | `/admin` with multi-category selector, show/hide, bulk edit |
| FSC sync | disabled |
| Admin seed at startup | disabled |

Backup taken on Fly before the join-table migration:

`/data/backup-before-agency-categories.json` (379 agencies, 29 categories).

## Current data model

Two category systems. Do not conflate them.

| Layer | Storage | Purpose |
| --- | --- | --- |
| Query routing | `langchain_pg_embedding` collection `query_categories` | Spoken/text query → category name (`Food`, `Shelter`, …) |
| Agency catalog | `categories` + `agency_categories` + legacy `agencies.category_id` | SQL lookup after routing |

Required schema on any Postgres this checkout uses:

1. `agencies.show_on_kiosk BOOLEAN NOT NULL DEFAULT TRUE` (revision `004`).
2. `agency_categories (agency_id, category_id)` PK, FK cascade, index on
   `category_id`, backfilled from non-null `agencies.category_id` (revision
   `005`).

Authoritative multi-category relation is `agency_categories`. Writes must:

- upsert category names
- replace join rows for that agency in the same transaction
- set `agencies.category_id` to the first selected category (or `NULL`)

## What the local agent must adjust

If this machine still has pre-005 code or schema, apply the same changes that
are already in this repo. Do not invent a parallel design.

### 1. Schema (local Postgres only)

If the appliance still runs local Postgres:

```sh
cd app/backend
DB_URI="<this machine's Postgres URI>" python main.py migrate
```

Confirm:

```sql
SELECT count(*) FROM agencies;                          -- expect existing catalog
SELECT count(*) FROM agency_categories;                 -- should equal agencies with a category
SELECT count(*) FROM agencies
 WHERE NOT EXISTS (
   SELECT 1 FROM agency_categories ac WHERE ac.agency_id = agencies.id
 );                                                     -- 0 if every row had category_id
```

Never run `seed-agencies --confirm-replace` against a populated catalog.

If this checkout already talks to canonical Neon through Fly, **do not migrate
Neon again**. Head is already `005`.

### 2. Voice SQL

[`app/backend/src/infrastructure/sql_agent/sql_executor.py`](../app/backend/src/infrastructure/sql_agent/sql_executor.py)
must join through `agency_categories` and use `SELECT DISTINCT` so a resource
assigned to two categories is returned once from either category. Do **not**
add `show_on_kiosk` to this query.

### 3. Browse directory

[`app/backend/src/infrastructure/agency_repository.py`](../app/backend/src/infrastructure/agency_repository.py)
must filter `a.show_on_kiosk = TRUE`. Directory output does not need category
arrays.

### 4. Admin API

Keep these contracts. If local code still has a singular `category` field,
update it.

- Read/write `categories: list[str]`. Accept legacy singular `category` on
  input.
- Filter admin lists with `EXISTS` on `agency_categories`, not
  `agencies.category_id`.
- Count category membership from the join table.
- Export column `categories` with `;` separators. Import still accepts
  `category` or `categories`.
- `PATCH /api/admin/agencies/bulk` updates up to 100 ids: replace categories
  and/or set `show_on_kiosk`. Superuser only.
- Publish-import still truncates `agencies, categories` with `CASCADE` (clears
  join rows via FK). That is intentional and destructive; do not run it
  casually against production Neon.

Key files:

- `app/backend/src/presentation/schemas.py`
- `app/backend/src/presentation/admin_routes.py`
- `app/backend/src/infrastructure/seeds/agency_seeder.py`

### 5. Admin UI

[`app/frontend/src/pages/AdminPage.jsx`](../app/frontend/src/pages/AdminPage.jsx)
must provide:

- searchable multi-category checkbox selector, with create-new-category
- category chips on each row
- per-row Browse eye toggle (`show_on_kiosk`)
- row checkboxes plus select-all on the current page
- bulk bar: show/hide Browse, replace categories, clear selection

API helper: `api.admin.bulkUpdateAgencies` in
[`app/frontend/src/lib/api.js`](../app/frontend/src/lib/api.js).

### 6. Runtime flags

On any local Compose/appliance `.env`:

```dotenv
KIOSK_MOCK_QUERY=false
FSC_RESOURCE_SYNC_ENABLED=false
TALKBOX_SEED_ADMIN=false
RESOURCE_SEARCH_MODE=category_vector_sql
```

`DB_URI` belongs only on the backend container. Prefer the same Neon URI the
Fly app uses for local verification; a local Postgres is allowed only when
deliberately configured and migrated to head.

## Files that already encode the correct behavior

Treat these as the source of truth. Copy their patterns; do not revert them.

| File | Why it matters |
| --- | --- |
| `app/backend/alembic/versions/004_agency_kiosk_visibility.py` | Browse flag |
| `app/backend/alembic/versions/005_agency_categories.py` | Join table + backfill |
| `app/backend/src/infrastructure/sql_agent/sql_executor.py` | Voice lookup |
| `app/backend/src/infrastructure/agency_repository.py` | Browse filter |
| `app/backend/src/presentation/admin_routes.py` | CRUD, import/export, bulk |
| `app/backend/src/presentation/schemas.py` | `categories[]`, bulk payload |
| `app/backend/src/infrastructure/seeds/agency_seeder.py` | Seed writes join rows |
| `app/frontend/src/pages/AdminPage.jsx` | Selector + bulk UI |
| `app/frontend/src/lib/api.js` | Admin client |
| `app/backend/tests/test_admin_visibility.py` | Visibility + multi-category tests |
| `app/backend/fly.toml` | Production flags |
| `AGENTS.md` | Product/routing rules |

CSV builder [`app/scripts/build_agencies_csv.py`](../app/scripts/build_agencies_csv.py)
still emits one `category` column and one row per `(agency, category)`. Leave
it unless the user asks to collapse duplicates. Live admin export is the
multi-category format.

## Search behavior to preserve

```text
user utterance
  -> pgvector query_categories (k=1)
  -> category name (Healthscout remaps to Medical Clinic)
  -> SQLExecutor via agency_categories
  -> up to 5 DISTINCT agencies
```

Browse:

```text
GET /api/kiosk/directory
  -> agencies WHERE show_on_kiosk = TRUE
```

Hidden resources remain voice-searchable and callable if they have a phone
number. Call allowlisting still happens server-side.

## Tests the local agent must run

```sh
cd app/backend && uv run pytest
cd app/frontend && npm run build
```

Minimum assertions already covered:

- `AdminAgencyWrite` accepts `categories[]` and legacy `category`
- import parses `Food; Housing`
- directory SQL includes `show_on_kiosk = TRUE`
- voice SQL includes `JOIN agency_categories` and `SELECT DISTINCT`, and does
  not mention `show_on_kiosk`
- admin mutations require `current_superuser`

After a local migrate, manually confirm:

1. Edit one resource to two categories in `/admin`.
2. Filter admin by either category; the resource appears once.
3. Voice/query for both category names returns it without duplicates.
4. Hide it from Browse; directory omits it; voice still finds it.
5. Bulk-select two rows, hide them, then show them again.

## What not to do

- Do not point kiosk Chromium at Vercel marketing routes.
- Do not upload backend secrets to Vercel (`VITE_*` only).
- Do not print `DB_URI`, admin passwords, or Fly tokens.
- Do not auto-apply Alembic from `docker-entrypoint.sh`.
- Do not change Twilio call authorization.
- Do not treat `docs/CODEBASE_AUDIT.md` notes about a future join table as
  current; the join table is already shipped.

## If the user asks for community-kiosk local copies next

That is a **new** project. Follow [`LOCAL_FIRST_KIOSK_SYNC.md`](LOCAL_FIRST_KIOSK_SYNC.md).
Any snapshot payload must include `show_on_kiosk` and `agency_categories` (or
an equivalent `categories: string[]` per agency). Local kiosk Postgres must
be at Alembic `005` before a snapshot swap. Neon credentials still never leave
Fly.

## Definition of done for this handoff

- Local schema is at `005` **or** this checkout uses Fly/Neon which already is.
- Voice SQL and Browse SQL match the files above.
- `/admin` can assign many categories and bulk-edit visibility/categories.
- Startup remains non-destructive.
- Kiosk UI, routes, and Twilio behavior are unchanged.
- No FSC sync, no second canonical database, no browser-held `DB_URI`.
