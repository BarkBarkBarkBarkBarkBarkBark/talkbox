# Talk Box

Shelter-oriented routing assistant. Users describe a need in plain English
("I need a shelter for tonight", "I'm a veteran looking for housing help");
Talk Box classifies the question with a pgvector similarity search, fetches the
relevant rows from the agencies/Healthscout datasets, and returns a structured
card grid to the caller (with a markdown fallback for SMS and other flat-text
clients).

**Entrypoint rule:** the production TalkBox kiosk is the main app. `/` is the
canonical public route and `/kiosk` is an alias to the same kiosk surface.
`/chat` is a secondary admin/partner console. Pointer/Health Scout remain
supporting routing/data assets, not the primary user-facing product.

---

## Monorepo layout

```
Talk Box/
├── backend/                        FastAPI + LangChain + Alembic + fastapi-users
│   ├── main.py                     explicit API, migration, import, vector CLI
│   ├── pyproject.toml + uv.lock    dependency manifest (uv)
│   ├── Dockerfile                  multi-stage alpine (builder + ~180 MB runtime)
│   ├── docker-entrypoint.sh        runtime setup only; never mutates catalog data
│   ├── alembic/                    migrations (schema owned by Alembic)
│   └── src/
│       ├── presentation/           FastAPI app, routers, Pydantic schemas, auth wiring
│       ├── application/services/   QueryHandler orchestrator, SMS async responder
│       ├── domain/services/        interfaces (IQueryCategorizer, IQueryExecutor, …)
│       └── infrastructure/
│           ├── config.py           pydantic-settings singleton
│           ├── db.py               to_sync_dsn() helper shared by all DB callers
│           ├── database.py         psycopg2 connection factory
│           ├── persistence/        async SQLAlchemy + User model (fastapi-users)
│           ├── llm/                factory: OpenAI or Bedrock chat + embeddings
│           ├── vector_store/       PGVectorQueryCategorizer
│           ├── sql_agent/          SQLExecutor (agencies lookup)
│           ├── healthscout_agent/  Healthscout provider extractor + SQLite lookup
│           ├── sms/                Twilio webhook client
│           ├── seed_admin.py       idempotent admin bootstrap
│           └── seeds/
│               ├── query_categories/*.json   30 routing seeds
│               ├── agencies_master.csv        301 shelter/social-service rows
│               ├── vector_seeder.py            embeds JSON into pgvector
│               └── agency_seeder.py            loads CSV into Postgres
├── frontend/                       React 19 + Vite 6 + Tailwind v4
│   ├── Dockerfile                  multi-stage node:22 → nginx:alpine
│   └── src/
│       ├── components/             UI primitives (ui/*), AppHeader, ChatMessage, ResultCards, ProtectedRoute
│       ├── pages/                  Kiosk / DemoKiosk / Chat
│       ├── hooks/useChat.js        chat state + API client
│       └── lib/                    api.js (fetch wrapper), auth.jsx (context), theme.jsx, utils.js (cn)
├── nginx/default.conf              reverse-proxy /api → backend:8000, SPA fallback
├── database/sacramento.db          Healthscout SQLite (17 k rows), baked into the backend image
├── csv/                            operational dumps (gitignored, e.g. healthscout_providers.csv)
├── scripts/
│   ├── README.md
│   └── rebuild_healthscout_db.py   uv-runnable CSV→SQLite rebuild tool (pandas)
├── docker-compose.yml              3 services (postgres + backend + frontend)
└── .github/workflows/deploy.yml    GHCR build matrix + self-hosted deploy
```

---

## Services (docker compose)

| Service            | Image                                          | Ports             |
|--------------------|------------------------------------------------|-------------------|
| `talkbox-postgres` | `pgvector/pgvector:pg18`                       | internal only     |
| `talkbox-backend`  | `ghcr.io/la-plas-growth/talkbox-backend`       | `:8000` expose    |
| `talkbox-frontend` | `ghcr.io/la-plas-growth/talkbox-frontend`      | `127.0.0.1:8084`  |

`talkbox-frontend` (nginx) serves the SPA and reverse-proxies `/api/*` to
`talkbox-backend:8000`. The Postgres port is **not** published on the host;
only the backend reaches it through the internal `talkbox-network`.

---

## Tech stack

### Backend
- **Python 3.13** (alpine), dependency manager: **uv** with a committed `uv.lock`
- **FastAPI 0.115** + **uvicorn** (standard extras)
- **SQLAlchemy 2.0** async (asyncpg) for the auth layer, **psycopg2** for SQL agent + seeders
- **Alembic** — owns the DDL (`001_initial`, `002_users`)
- **fastapi-users[sqlalchemy] 14** — cookie-JWT auth with a custom User model
- **LangChain 0.3** + factory dispatch (OpenAI `ChatOpenAI` or AWS Bedrock `ChatBedrockConverse`)
- **pgvector** via `langchain-postgres.PGVector`
- **Twilio** for the SMS webhook

### Frontend
- **React 19** + **Vite 6**
- **Tailwind CSS v4** with CSS variables + `@theme inline` mapping (teal brand palette)
- **Radix UI** (DropdownMenu, Separator, Slot) + **lucide-react** icons
- **class-variance-authority** + **tailwind-merge** + **clsx** for the component library
- **react-router-dom v7**, **react-markdown** + `remark-gfm`, **sonner** for toasts
- **Inter** font via Google Fonts preconnect

### Infra
- **pgvector/pgvector:pg18** (single mount at `/var/lib/postgresql`, pg18 layout)
- **nginx:alpine** (reverse proxy + SPA static server)
- **GitHub Actions** self-hosted runners on the `Oracle` group
- **Cloudflare Tunnel** terminates HTTPS in front of the frontend

---

## HTTP surface

Public:
- `GET  /api/health`                — liveness
- `POST /api/sms-query`             — Twilio webhook (form-encoded `Body`, `From`)
- `POST /api/auth/register`         — JSON `{email, password, name, company?}` → 201
- `POST /api/auth/jwt/login`        — `application/x-www-form-urlencoded` `username=<email>&password=<…>` → 204 + httpOnly cookie `talkbox_auth`
- `POST /api/auth/jwt/logout`       — clears the cookie

Authenticated (requires `talkbox_auth` cookie):
- `POST /api/query`                 — body `{"query": "..."}` → `{"markdown": "...", "results": {...}}`
- `GET  /api/users/me`              — current profile
- `PATCH /api/users/me`             — update name/company/password

### `POST /api/query` response shape

```jsonc
{
  "markdown": "**River Oak Center for Children, Inc.**\nChildren's General & …",
  "results": {
    "type": "agencies",             // or "doctors"
    "category": "Mental Health Clinic",
    "items_agencies": [
      { "name": "...", "phone": "...", "address": "...",
        "description": "...", "insurance": "...", "tags": "..." }
    ],
    "items_doctors": []
  }
}
```

The SPA renders `results` as a card grid (1 col mobile / 2 col sm+) with
`tel:` links on phone numbers. Non-SPA clients (Twilio SMS) fall back to the
`markdown` field, which stays a compact, legible summary.

---

## Multi-provider LLM

Two env switches drive the whole stack:

| Switch                | Values              | Affects                            |
|-----------------------|---------------------|------------------------------------|
| `LLM_PROVIDER`        | `openai` \| `bedrock` | Chat completion (`HealthScoutExtractor`) |
| `EMBEDDINGS_PROVIDER` | `openai` \| `bedrock` | Embeddings (seeder + runtime categorizer) |

### Chat model catalog

| Provider  | `MODEL` examples                                                                 | Required env                                                  |
|-----------|-----------------------------------------------------------------------------------|----------------------------------------------------------------|
| `openai`  | `gpt-4o-mini`, `gpt-4o`                                                           | `OPENAI_API_KEY`                                               |
| `bedrock` | `eu.anthropic.claude-haiku-4-5-20251001-v1:0`, `us.anthropic.claude-sonnet-4-5-…` | `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`      |

### Embeddings catalog

| Provider  | `EMBEDDINGS_MODEL`                                                                      | Vector dim |
|-----------|------------------------------------------------------------------------------------------|------------|
| `openai`  | `text-embedding-3-small` (default), `text-embedding-3-large`                             | 1536 / 3072 |
| `bedrock` | `amazon.titan-embed-text-v2:0`, `cohere.embed-english-v3`, `cohere.embed-multilingual-v3` | 1024       |

> Swapping the embeddings provider changes the vector dimension. pgvector
> rejects a similarity search against a mismatched collection. When you
> rotate the provider, **also rotate `COLLECTION_NAME`** (e.g.
> `query_categories_titan`) so the seeder writes to a fresh collection. The
> old one stays in the DB, unused.

---

## Database lifecycle

Normal backend startup does not run migrations, import CSV data, or create
embeddings. These operations are explicit so a restart cannot overwrite a
curated catalog. `install.sh` initializes a local database only when the
`agencies` table is empty; it leaves every populated catalog unchanged.

For Neon setup and production migration, follow
[`docs/NEON_MIGRATION.md`](docs/NEON_MIGRATION.md). Do not run catalog replacement
commands against an existing production database without a verified backup.

---

## CLI reference (backend)

```bash
python main.py api             # start uvicorn
python main.py migrate         # alembic upgrade head
python main.py seed-category-vectors
python main.py seed-agency-vectors
python main.py seed-agencies --confirm-replace
python main.py seed-agencies --confirm-replace --csv /path/to/alt.csv
```

`seed-agency-vectors` downloads the authenticated FSC TalkBox bootstrap,
embeds each published and visible resource, and writes its canonical
`resource_id` into vector metadata. It requires `DB_URI`,
`FSC_RESOURCE_API_BASE_URL`, `FSC_RESOURCE_API_KEY`, and the configured
embeddings-provider credentials. Seed a fresh `AGENCY_COLLECTION_NAME`, verify
it, then deploy that collection name with `RESOURCE_SEARCH_MODE=vector`.

Kiosk query responses include `search_mode`. A value of `vector` confirms
near-text retrieval; `lexical_fallback` means the collection was unavailable,
empty, stale, or did not map to the current FSC snapshot.

Inside a running container:

```bash
sudo docker exec talkbox-backend \
  python main.py seed-agencies --confirm-replace
```

---

## Local development

### Full stack via docker compose

```bash
cp .env.example .env
# fill POSTGRES_PASSWORD, OPENAI_API_KEY (+ AWS_* if LLM/EMBEDDINGS_PROVIDER=bedrock)

docker compose up --build
```

- Frontend → <http://localhost:8084>
- API health (via nginx) → <http://localhost:8084/api/health>
- Log in with `ADMIN_EMAIL` + `ADMIN_PASSWORD` from `.env` (lifespan seeds it
  on first boot).

### Backend only

Dependencies are managed with **uv**. Install it once
(`curl -LsSf https://astral.sh/uv/install.sh | sh`), then:

```bash
cd backend
uv sync
DB_URI=postgresql+psycopg://talkbox:secret@localhost:5432/talkbox \
  uv run python main.py api --reload
```

### Frontend only

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

Vite's dev server proxies `/api/*` to `VITE_API_URL` so you can point it at a
local backend or a remote staging deployment.

---

## Configuration

`.env.example` at the repo root is the source of truth. Grouped by area:

| Group      | Keys                                                                                       |
|------------|--------------------------------------------------------------------------------------------|
| Postgres   | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`                                         |
| LLM        | `LLM_PROVIDER`, `MODEL`, `MODEL_TEMPERATURE`                                                |
| Embeddings | `EMBEDDINGS_PROVIDER`, `EMBEDDINGS_MODEL`, `COLLECTION_NAME`                                |
| OpenAI     | `OPENAI_API_KEY`                                                                           |
| AWS        | `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`                                  |
| Database   | `DB_URI`, `DB_NAME`, `DB_TABLE_NAME`                                                        |
| Logging    | `LOG_FILE`, `LOG_LEVEL`                                                                    |
| HTTP       | `CORS_ORIGINS`                                                                             |
| Auth       | `JWT_SECRET`, `COOKIE_SECURE`, `FRONTEND_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME`, `ADMIN_COMPANY` |
| Twilio     | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`                            |
| Frontend   | `VITE_API_URL`, `VITE_APP_NAME`                                                            |
| Docker     | `IMAGE_BACKEND`, `IMAGE_FRONTEND` (overridden by CI)                                        |

---

## CI/CD

`.github/workflows/deploy.yml` triggers on `push` to `main` / `develop` and on
`workflow_dispatch`. It runs on the **self-hosted `Oracle` runner group**.

### `build-and-publish`

Matrix over `backend` + `frontend`:
- Builds with **Buildx** + GHA cache (`cache-from type=gha,scope=<svc>`).
- Tags each image with `{branch}`, `sha-short`, and `latest` on the default branch.
- Frontend receives `VITE_API_URL` / `VITE_APP_NAME` as build-args from GitHub
  Actions vars; the backend bakes `alembic/`, the query-category JSONs,
  `agencies_master.csv`, and `database/sacramento.db` into the image so the
  seed step and Healthscout lookups are self-sufficient.
- Pushes to `ghcr.io/la-plas-growth/talkbox-{backend,frontend}`.

### `deploy`

Runs after `build-and-publish` on the same self-hosted runner:
1. Copies `docker-compose.yml` and `nginx/default.conf` to `/opt/talkbox` on
   the host.
2. Renders `/opt/talkbox/.env` from GitHub **secrets** (passwords, keys,
   DB_URI) + **vars** (non-sensitive config) with permission `600`.
3. `docker compose pull && docker compose up -d --remove-orphans`.
4. Prunes stale images.

`workflow_dispatch` accepts `skip_build=true` to re-deploy the current GHCR
tags without rebuilding.

### GitHub environment `production`

Set via `gh secret set ... --env production` / `gh variable set ... --env
production`:

| Kind    | Name                                                                                                      |
|---------|-----------------------------------------------------------------------------------------------------------|
| Secret  | `POSTGRES_PASSWORD`, `DB_URI`, `OPENAI_API_KEY`, `JWT_SECRET`, `ADMIN_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` |
| Variable | `POSTGRES_DB`, `POSTGRES_USER`, `LLM_PROVIDER`, `MODEL`, `MODEL_TEMPERATURE`, `EMBEDDINGS_PROVIDER`, `EMBEDDINGS_MODEL`, `COLLECTION_NAME`, `AWS_REGION`, `DB_NAME`, `DB_TABLE_NAME`, `LOG_FILE`, `LOG_LEVEL`, `CORS_ORIGINS`, `COOKIE_SECURE`, `FRONTEND_URL`, `ADMIN_EMAIL`, `ADMIN_NAME`, `VITE_APP_NAME` |

### Public hostname via Cloudflare Tunnel

`cloudflared` runs on the VM and maps a public hostname (e.g.
`talkbox.laplasgrowth.com`) to `http://127.0.0.1:8084`. The SPA + API are
served through the same origin — nginx routes `/api/*` to the backend and
everything else to the SPA, so the cookie is always same-origin and no CORS
dance is needed in the browser.

Example `cloudflared` ingress:

```yaml
ingress:
  - hostname: talkbox.laplasgrowth.com
    service: http://127.0.0.1:8084
  - service: http_status:404
```

---

## Operational scripts

### `scripts/rebuild_healthscout_db.py`

Rebuilds `database/sacramento.db` from a fresh Healthscout CSV dump. Not part
of the startup flow — run it manually when a new dump arrives:

```bash
uv run scripts/rebuild_healthscout_db.py \
    --csv  csv/healthscout_providers.csv \
    --out  database/sacramento.db
sudo docker restart talkbox-backend   # pick up the new file (bind mount is RO)
```

Uses pandas; `uv` pulls it into an ephemeral venv thanks to the PEP 723
inline metadata inside the script. See `scripts/README.md` for details.

---

## Admin bootstrap

`backend/src/infrastructure/seed_admin.py` runs inside the FastAPI lifespan.
Behavior:
- If `ADMIN_EMAIL` already exists in `users`, no-op.
- Otherwise, create a row with `is_active=is_superuser=is_verified=True`,
  password hashed with `fastapi_users.password.PasswordHelper`.

To rotate the admin password after the first seed:

```bash
# From the host — updates the row in-place
sudo docker exec -i talkbox-postgres psql -U talkbox -d talkbox -c \
  "UPDATE users SET hashed_password=... WHERE email='admin@laplasgrowth.com';"
# (or log in as admin and PATCH /api/users/me {"password": "..."})
```

Then update `ADMIN_PASSWORD` in the GitHub production environment so future
rebuilds stay consistent.

---

## Troubleshooting

| Symptom                                                                   | Cause / fix                                                                                           |
|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| `talkbox-postgres` dies immediately on first boot                         | `pgvector/pgvector:pg18` wants the single-mount layout. `docker-compose.yml` already mounts `/var/lib/postgresql` (not `/data`); a lingering volume from a previous pg16 setup needs `docker compose down -v`. |
| `/api/users/me` returns 500 right after login                             | Admin email set to a reserved TLD (`.local`, `.test`). pydantic `EmailStr` rejects it. Use a routable TLD like `@example.com` or your own domain. |
| All non-Healthscout queries return "No valid result found"                | `DB_URI` still uses the SQLAlchemy-prefix `postgresql+psycopg://` and psycopg2 refuses it. `src/infrastructure/db.to_sync_dsn` strips the prefix — make sure every DB call routes through it. |
| Seeder re-embeds on every boot                                            | Smart-skip only matches on row count; changing `EMBEDDINGS_MODEL` without rotating `COLLECTION_NAME` leaves the old count in place. Set a new `COLLECTION_NAME` when you swap provider. |
| `docker build` fails on pip resolve                                       | The Dockerfile uses `uv sync --frozen` against `uv.lock`. If you edited `pyproject.toml`, regenerate the lock with `uv lock` and commit it. |
| GitHub Actions run stays `queued` forever                                 | `runs-on` must match the Oracle runner group label (`runs-on: [group: Oracle]`), not bare `self-hosted`. |

---

## License

Proprietary — internal use at la-plas-growth. Third-party components retain
their respective licenses.
