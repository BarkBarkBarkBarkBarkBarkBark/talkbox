You are working in my existing **TalkBox** repository.

Your job is to inspect the current system, then make the smallest sensible set of changes required to make the existing standalone Neon Postgres database the canonical remote database for TalkBox, run the application locally against it, and verify that the website/kiosk demo is actually reaching the remote backend and remote Neon data.

## Important context

Do NOT build or integrate the Grove resource database right now.

I am abandoning that integration for the moment.

The canonical resource database should be my existing standalone Neon project named:

`talkbox`

This database already exists and already contains real TalkBox data, including approximately:

* 379 agencies/resources
* 29 categories
* existing pgvector/LangChain tables
* existing user/auth tables

Do NOT create a new database and do NOT replace or wipe the existing Neon data.

The existing application appears to already have:

* FastAPI backend
* React/Vite frontend
* PostgreSQL support
* Alembic
* LangChain + pgvector
* a kiosk API
* existing authentication
* existing resource/agency querying
* environment-variable-based database configuration

Known relevant areas of the repo include:

* `app/backend/`
* `app/frontend/`
* `app/backend/src/infrastructure/config.py`
* `app/backend/src/application/services/kiosk_query_service.py`
* `app/backend/src/infrastructure/vector_store/pgvector_query_categorizer.py`
* `app/frontend/src/lib/kioskApi.js`
* `app/backend/fly.toml`
* `.env.example`

Do not assume those paths or implementations are still correct; inspect the current repo first.

# Goal

I want this architecture:

TalkBox Neon
→ canonical remote data store

FastAPI backend
→ connects to TalkBox Neon

TalkBox website/kiosk frontend
→ talks only to the FastAPI API

Local development
→ also uses the same canonical TalkBox Neon database unless explicitly configured otherwise

Eventually I will create:

`talk-box.org/admin`

for managing resources and kiosk presentation, but that is NOT the primary task yet.

First I need the database/backend/frontend plumbing to be clean and verified.

# Phase 1 — Inspect before modifying anything

Inspect the repository and determine:

1. How the backend currently obtains its PostgreSQL connection string.
2. Which environment variable is canonical (`DB_URI`, `DATABASE_URL`, or something else).
3. Whether Docker Compose currently launches its own local PostgreSQL container.
4. Whether application startup automatically seeds, truncates, migrates, or otherwise modifies the database.
5. Whether connecting the application to the existing Neon production database could accidentally:

   * truncate agencies
   * reseed agencies
   * overwrite categories
   * overwrite vector embeddings
   * create an admin user
   * run destructive migrations
6. How the local frontend determines its backend URL.
7. How the deployed/demo frontend determines its backend URL.
8. Where the currently deployed TalkBox backend runs.
9. What API endpoints currently exist for:

   * health
   * kiosk config
   * kiosk resources/search
   * normal resource querying
10. Whether CORS, reverse proxies, authentication, or deployment configuration would prevent the website demo from calling the backend directly.

Before making substantive changes, summarize your findings.

Pay particular attention to startup/bootstrap code. I do NOT want pointing the application at Neon to accidentally reset the existing 379-resource database.

# Phase 2 — Establish Neon as canonical

After inspection, configure the application so the existing standalone Neon `talkbox` project is the canonical database.

Requirements:

* Database credentials must remain server-side.
* Never expose the Neon connection string to browser JavaScript.
* The React frontend should communicate with FastAPI, not directly with PostgreSQL.
* Use environment variables for the Neon connection string.
* Keep secrets out of Git.
* Prefer the existing database configuration abstraction instead of adding a second parallel mechanism.
* Preserve the existing production data.
* Do not run destructive seed operations against the remote database.

If the current application startup automatically seeds or truncates data, separate:

**schema migration**

from

**development/demo seeding**

so production/remote Neon startup is safe.

There should be an obvious mode in which the backend can start against an already-populated Neon database without modifying its contents.

If `TALKBOX_SKIP_BOOTSTRAP` or a similar mechanism already exists, evaluate whether it is sufficient rather than inventing another one.

# Phase 3 — Run locally against Neon

Get the backend running locally while connected to the existing remote Neon TalkBox database.

Verify using actual queries/API responses that it is reading the remote data.

I want concrete evidence such as:

* successful database connectivity
* agency/resource count matching the remote database approximately
* category count
* successful retrieval of one known resource
* successful `/api/health`
* successful kiosk/resource query

Do NOT prove connectivity by writing test garbage into the production database.

Read-only verification is preferred.

# Phase 4 — Run the frontend locally

Start the TalkBox frontend locally and point it at the local FastAPI backend.

Verify the complete path:

Browser
→ React/Vite frontend
→ FastAPI
→ remote Neon

Use the actual UI, not only curl/API tests.

Test at minimum:

1. Application loads.
2. Backend health succeeds.
3. A resource/search request succeeds.
4. Results shown in the browser came from the Neon-backed API.
5. Browser console has no relevant network/CORS errors.

If the current kiosk demo has a mock mode, make sure we are NOT accidentally testing mock data.

Identify every configuration switch that can cause mock/fallback resources to appear.

# Phase 5 — Verify the website/demo deployment

Determine how the current public/demo frontend is deployed and what backend URL it calls.

Then make sure the public website/demo uses the real deployed FastAPI API backed by the same TalkBox Neon database.

The desired production path is:

Public TalkBox website
→ HTTPS TalkBox backend API
→ canonical TalkBox Neon DB

Check:

* frontend API base URL
* backend deployment URL
* HTTPS
* CORS
* health endpoint
* production environment variables
* production Neon connection
* mock-mode settings
* whether the frontend deployment needs to be rebuilt/redeployed

Do not guess that it works because environment variables look right.

Actually verify the network request from the demo/browser if tooling permits.

# Phase 6 — Prepare for the future admin interface

Do NOT build the full admin interface unless it is trivial after the above work.

Instead, after the system is verified, tell me what needs to happen next to support:

`talk-box.org/admin`

The future admin needs to manage the canonical TalkBox resources.

Likely desired resource controls include:

* resource name
* description
* short kiosk description
* phone
* address
* category
* show on kiosk home screen
* kiosk home ordering
* searchable via semantic search
* callable from kiosk
* active/archive status
* last verified date

Also evaluate the current semantic search architecture.

I believe the current pgvector implementation may embed approximately 30 query categories and use nearest-neighbor search only to select a category, followed by SQL lookup.

My desired future behavior is different:

User asks:
“I need somewhere I can sleep tonight and I have a dog”

→ embed user query

→ compare against RESOURCE embeddings

→ return the nearest actual resources

So inspect the current vector pipeline and tell me exactly what would need to change to support one embedding/document per resource.

Do not implement a large RAG framework. We have only hundreds of resources and should keep this simple.

# Guardrails

Do NOT:

* create a new Neon project
* migrate the Grove/Replit database
* delete existing TalkBox data
* truncate the production agencies table
* automatically reseed the production database
* expose PostgreSQL credentials to the frontend
* rebuild the application unnecessarily
* introduce another auth framework
* introduce another database abstraction unless truly required
* add infrastructure just because it is fashionable

Prefer the lowest-friction modification of the existing system.

# Deliverables

At the end, give me:

## 1. Current architecture

A short explanation of what you found.

## 2. Changes made

Exactly what you changed and why.

## 3. Database safety

Explain how you ensured that starting TalkBox against Neon cannot accidentally erase or reseed the canonical resource data.

## 4. Local verification

Show evidence that:

React frontend
→ local FastAPI
→ remote Neon

works.

## 5. Public demo verification

Show evidence that:

public/demo frontend
→ deployed FastAPI
→ remote Neon

works, or clearly identify the remaining blocker.

## 6. Configuration map

List the relevant environment variables and where each belongs:

* local backend
* local frontend
* deployed backend
* deployed frontend

Do not print secret values.

## 7. Next implementation step

Give me the smallest next task required to build `/admin`.

## 8. Semantic search recommendation

Explain the minimal migration from category-vector routing to direct resource-vector similarity search.

# Working style

Inspect first.

Make incremental changes.

Test after each meaningful change.

If something already works, keep it.

If you discover that my assumptions above are wrong, follow the repository as the source of truth and explain the discrepancy.

The priority is to get a boring, understandable pipeline working:

**one canonical Neon database → one backend API → every TalkBox client.**
