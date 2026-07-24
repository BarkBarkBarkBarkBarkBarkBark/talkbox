# TalkBox Simplification, Code Audit, and Production Hardening Handoff

Repository:

`BarkBarkBarkBarkBarkBarkBark/talkbox`

## Primary objective

This project has accumulated complexity through rapid iterative development.

Your job is **not to add features**.

Your job is to:

> Reduce complexity, identify hidden failure modes, establish one obvious source of truth for resource data, and make the system safe to deploy to multiple Raspberry Pi TalkBox kiosks.

Favor deletion, consolidation, deterministic behavior, explicit failures, and boring architecture.

Do not preserve complexity merely because it already exists.

---

# Guiding principle

The desired production architecture is conceptually:

```text
Human editors
      |
      v
Web resource admin
      |
      v
Canonical Neon Postgres
      |
      v
Central backend/API
      |
      +----------+----------+----------+
      |          |          |          |
   TalkBox 1  TalkBox 2  TalkBox 3  TalkBox N
```

There must be:

* ONE authoritative resource database.
* ONE obvious production query path.
* ONE obvious admin/editing path.
* NO silent fallback to fake/mock resources.
* NO destructive automatic reseeding.
* NO random production search results.
* NO kiosk capable of overwriting canonical resource data simply because it rebooted.
* NO requirement to SSH into a Raspberry Pi to maintain resource information.

A TalkBox should be a replaceable appliance, not a database authority.

---

# IMPORTANT SAFETY CONSTRAINT

There is currently at least one physical Raspberry Pi TalkBox that works.

Do not brick it while refactoring.

Before changing implementation:

1. Audit first.
2. Document current behavior.
3. Identify the exact deployment path used by the physical Pi.
4. Identify all persistent state on the Pi.
5. Identify all secrets/configuration needed to restore it.
6. Identify what `talkbox update`, Docker Compose, install scripts, kiosk startup, Twilio sync, Tailscale, and systemd components currently do.
7. Produce a rollback procedure.

Do not perform destructive database operations.

Do not modify production data.

Do not delete a working deployment mechanism until its replacement has been tested independently.

Do not push directly to `main`.

Work on a dedicated simplification branch.

Treat the existing physical kiosk as an appliance that must continue working during this project.

---

# PHASE 1 — AUDIT ONLY

Before implementing anything, perform a serious code review.

Create:

`docs/CODEBASE_AUDIT.md`

This document is intended for a technically learning human owner who wants to understand the codebase.

Make it comprehensive but plainspoken.

Do not merely list files.

Explain how the application actually works.

## Section 1 — Architecture map

Describe:

* frontend
* backend
* PostgreSQL
* pgvector
* SQLite/HealthScout database
* Twilio
* speech-to-text
* authentication
* Docker
* Raspberry Pi deployment
* Fly/Vercel if still relevant
* Neon if configured or historically configured
* Tailscale
* seed/import pipeline

Include a simple ASCII architecture diagram.

For each component answer:

* Why does this exist?
* Is it used in production?
* Who owns its state?
* Can it be deleted or simplified?

---

# Section 2 — Trace the exact kiosk query path

Trace a request from:

```text
User presses quick-resource button
```

and separately:

```text
User speaks/types natural-language request
```

all the way through:

```text
frontend
→ HTTP endpoint
→ service
→ categorization
→ database
→ result formatting
→ screen
```

List every file/function involved.

Explicitly determine:

### When does `kiosk_mock_catalog.json` get used?

Known suspicious behavior to verify:

`KioskQueryService.query()` appears to:

1. use mock data when `KIOSK_MOCK_QUERY=true`
2. attempt the real query otherwise
3. catch a broad `Exception`
4. silently return mock data when the real query fails

This is considered a serious production foot gun.

Confirm exactly what happens.

Identify every circumstance where the kiosk can display mock data while appearing healthy.

Determine whether the currently deployed Pi is actually querying Postgres or silently using the mock catalog.

Recommend a direct method for proving the source of every returned resource.

---

# Section 3 — Identify every source of truth

Find every place resource information can currently live.

At minimum inspect:

* `agencies_master.csv`
* `kiosk_mock_catalog.json`
* PostgreSQL `agencies`
* PostgreSQL `categories`
* pgvector collections
* `database/sacramento.db`
* source datasets under `Datasets/`
* generated CSVs
* generated mock snapshots
* any hardcoded 211 records
* any hardcoded menu/category data

Create a table:

| Data | Current authority | Generated from | Runtime consumer | Should remain? |
| ---- | ----------------- | -------------- | ---------------- | -------------- |

Answer:

> If I manually correct the phone number for an agency today, where must I change it so the correction persists forever?

If the answer is more than one place, flag it.

---

# Section 4 — Database lifecycle audit

Trace what happens during:

```text
fresh install
boot
container restart
talkbox restart
talkbox update
git pull
Docker rebuild
backend startup
migration
seed
```

Pay special attention to:

```text
python main.py seed
seed_agencies()
TRUNCATE agencies, categories
```

Determine whether startup or deployment can destroy manually curated database changes.

This is CRITICAL severity if confirmed.

Explain the exact sequence in plain English.

---

# Section 5 — Complexity inventory

Find:

* duplicate abstractions
* obsolete files
* historical deployment paths
* duplicate database access layers
* unused classes
* dead configuration variables
* mock/demo code leaking into production
* duplicate API routes
* generated files committed as canonical data
* unnecessary LLM involvement
* unnecessary pgvector involvement
* multiple persistence libraries doing the same job
* broad exception handlers
* silent fallback behavior
* unnecessary feature flags
* stale documentation
* stale Fly/Vercel/Docker assumptions
* code that exists only because an earlier architecture required it

Do not assume an abstraction is useful just because it has a nice class name.

For every item classify:

```text
KEEP
SIMPLIFY
MERGE
DELETE
UNKNOWN — investigate
```

---

# Section 6 — Issue register

Create a ranked issue table:

| ID | Severity | Area | Problem | Consequence | Recommended fix |
| -- | -------- | ---- | ------- | ----------- | --------------- |

Use:

```text
CRITICAL
HIGH
MEDIUM
LOW
```

CRITICAL includes anything that can:

* destroy canonical data
* silently return fake data
* allow unsafe dialing
* expose secrets
* prevent recovery of deployed kiosks
* let one kiosk corrupt shared infrastructure

---

# Section 7 — Explain the codebase to me

Write a section called:

## "The 20% of this codebase I need to understand to understand 80% of TalkBox"

Identify approximately 10–20 key files.

For each give:

```text
FILE
PURPOSE
WHO CALLS IT
WHAT IT CALLS
STATE IT OWNS
CAN IT BE SIMPLIFIED?
```

Then provide:

### Suggested reading order

Number the files in the order a developer should study them.

The goal is for a human who did not originally write the architecture intentionally to gain a mental model of the codebase.

---

# PHASE 2 — PROPOSE THE MINIMUM PRODUCTION ARCHITECTURE

After completing the audit, propose the smallest reasonable production architecture.

Do not implement it yet.

Prefer:

```text
React frontend
FastAPI backend
Neon PostgreSQL
Twilio
optional OpenAI/embedding service only where clearly useful
```

Question whether every other moving part is necessary.

---

# Canonical database requirement

The desired architecture is:

```text
Neon PostgreSQL = canonical resource source of truth
```

All production TalkBoxes should see the same canonical resources.

Do not run independent mutable resource databases on individual Raspberry Pis.

The Pi should not own canonical agency/resource state.

Prefer:

```text
Pi/browser
→ central authenticated/controlled API
→ Neon
```

over:

```text
Pi
→ privileged direct Neon credentials
```

Explain the tradeoff.

---

# Neon setup recommendation

Provide an exact human-oriented guide for creating the Neon database.

Include:

1. Create Neon project.
2. Create production database/branch.
3. Enable required PostgreSQL extensions such as pgvector only if still needed.
4. Create least-privilege application roles.
5. Explain direct vs pooled connection strings.
6. Configure backend `DB_URI`.
7. Run Alembic migrations explicitly.
8. Import initial agency data once.
9. Verify row counts.
10. Verify the backend reads from Neon.
11. Restart the backend.
12. Verify data remains unchanged.
13. Restart/rebuild the Pi.
14. Verify data remains unchanged.

Never place unrestricted admin database credentials in the kiosk frontend.

Document recovery procedures before calling the migration complete.

---

# Neon visual inspection

The technical owner should be able to use the Neon Console Tables interface to:

* inspect tables
* filter records
* manually edit values
* inspect schema

But this should be treated as a developer/admin tool.

Do NOT make ordinary nontechnical staff Neon database administrators.

---

# NONTECHNICAL RESOURCE EDITING

Design the simplest possible authenticated web interface.

Call it something like:

```text
/admin/resources
```

This is not a CMS project.

It should feel like a safe spreadsheet.

Minimum functionality:

```text
Search resources
Filter resources
View resource
Edit resource
Add resource
Disable resource
Mark verified
```

Avoid hard deletion for normal users.

Prefer:

```text
status = active / inactive / unverified
```

over deleting rows.

Minimum useful fields should be evaluated, likely including:

```text
name
phone
address
website
description
category/categories
status
source
source_url
last_verified_at
updated_at
```

Do not add dozens of fields unless existing data requires them.

The admin UI must use backend CRUD endpoints.

The browser should never contain database credentials.

Use the existing authentication system if it is adequate rather than introducing another auth platform.

Restrict write operations to authorized admin/editor users.

---

# SINGLE SOURCE OF TRUTH RULE

After migration:

```text
Neon/Postgres
```

must be authoritative.

CSV files may be:

```text
IMPORT INPUT
EXPORT
BACKUP
FIXTURE
```

They must NOT overwrite production automatically.

Mock JSON may be:

```text
TEST FIXTURE
```

or preferably deleted if no longer useful.

It must NOT participate in production runtime behavior.

---

# REMOVE PRODUCTION MOCK FALLBACK

The desired behavior is:

```text
Database working
→ real results

Database unavailable
→ explicit controlled failure
→ offer Call 211
→ log/alert error
```

NOT:

```text
Database unavailable
→ silently display mock agencies
```

Remove production dependency on:

`kiosk_mock_catalog.json`

Remove or isolate:

`KIOSK_MOCK_QUERY`

unless there is a compelling test-only reason to retain it.

Tests can use explicit test fixtures.

Demo behavior must not silently exist inside production behavior.

If `/demo` requires fake resources, isolate that behavior completely from `/kiosk`.

---

# REMOVE RANDOM RESULTS

Find:

```sql
ORDER BY RANDOM()
```

Remove it from production resource selection.

Do not replace it with a complicated recommendation engine during this simplification project.

Use the simplest deterministic ordering that makes sense.

For example:

```text
explicit priority if it already exists
then stable name/id ordering
```

If ranking quality needs future work, document it separately.

The immediate requirement is:

> The same query against unchanged data should produce predictable results.

Do not use randomness to hide weak retrieval logic.

---

# SIMPLIFY RESOURCE QUERYING

Audit whether this pipeline is justified:

```text
natural language
→ embedding
→ pgvector category
→ SQL category lookup
→ random 5 records
```

Do not automatically remove semantic search.

But evaluate whether the implementation can be simpler.

Separate two concerns:

```text
1. Determine what the user needs
2. Retrieve appropriate resources
```

Do not let embeddings become a second source of resource truth.

Embeddings/categories can assist routing.

Canonical agency facts must come from PostgreSQL.

---

# SIMPLIFY DATABASE ACCESS

The repo appears to use combinations of:

* SQLAlchemy async
* psycopg
* possibly psycopg2 historical paths
* Alembic
* LangChain Postgres/pgvector

Audit whether multiple database libraries are necessary.

Prefer one clear application persistence approach where practical.

Do not perform a risky rewrite merely for stylistic consistency.

Recommend consolidation only where it materially reduces maintenance burden.

---

# FIX DATABASE SEEDING

Production startup should conceptually be:

```text
start
→ verify configuration
→ run safe schema migrations if explicitly intended
→ connect to existing canonical DB
→ serve
```

NOT:

```text
start
→ truncate canonical data
→ reload CSV
→ serve
```

Create explicit separate concepts:

```text
bootstrap database
import data
run application
```

They must not be conflated.

Initial bootstrap/import should require deliberate operator action.

Normal application startup must be non-destructive.

---

# IMPORT SAFETY

Future external datasets must not directly replace canonical human-curated records.

Recommend a minimal staging pattern:

```text
external source
→ staging/import
→ compare/review
→ approved canonical update
```

Do not build the full scraper platform now.

Just make the architecture capable of supporting it later.

Manual human curation is currently more important than automation.

---

# DATA MODEL REVIEW

Review the current schema critically.

Specifically investigate:

### One-category-per-agency limitation

Current schema appears to use:

```text
agencies.category_id
```

Determine whether real organizations need multiple categories.

Do not blindly redesign.

Explain the migration cost and whether a many-to-many:

```text
agencies
categories
agency_categories
```

would materially improve correctness.

### Phone numbers

Calling is a core TalkBox function.

Determine whether storing one arbitrary string phone field is sufficient.

Flag cases where:

* multiple numbers exist
* extensions exist
* intake and main numbers differ
* phone data is embedded inside descriptions

Recommend the minimum sensible normalization.

Do not overengineer.

---

# OBSERVABILITY

The system must make its data source obvious.

For development/admin diagnostics, provide a way to determine:

```text
backend version
database host/database identity
catalog row count
database connectivity
mock mode status
last successful query source
```

Never expose secrets.

A health endpoint should distinguish:

```text
process alive
```

from:

```text
production dependencies healthy
```

Do not let a healthy HTTP process hide a dead database.

---

# PI SAFETY / ANTI-BRICK PLAN

Before touching Pi deployment behavior, document:

```text
Current boot sequence
Docker services
systemd units
kiosk session startup
Chromium startup
button bridge
audio configuration
Twilio sync
Tailscale
network configuration
persistent volumes
environment files
secrets
```

Create:

## Pi rollback checklist

At minimum:

```text
How to identify last known-good git commit
How to check out/redeploy it
How to preserve .env
How to preserve device-specific configuration
How to restart containers
How to verify microphone
How to verify speaker
How to verify keypad/buttons
How to verify Twilio calling
How to verify resource search
How to verify 211 fallback
```

Do not make the Pi database migration a prerequisite for booting the kiosk UI.

A failed central API should degrade gracefully to:

```text
Call 211 still available
clear service-unavailable messaging
```

rather than rendering the kiosk unusable.

---

# DEPLOYMENT SIMPLIFICATION

Audit whether all current deployment targets are still necessary.

There may be historical overlap between:

```text
local Docker
Raspberry Pi
Fly.io
Vercel
GHCR
self-hosted runners
Cloudflare
Tailscale
```

Do not assume they all need to survive.

Identify the intended production model.

Recommend the fewest moving parts that satisfy:

```text
web frontend
central backend
Neon database
Twilio webhook accessibility
physical Raspberry Pi kiosk
safe remote updates
```

Mark obsolete deployment paths for removal.

Do not delete anything until current usage is verified.

---

# TECHNICAL-DEBT DELETION LIST

Create a section:

## What I would delete

For every candidate include:

```text
file/component
reason
evidence it is unused or harmful
risk of deletion
verification required before deletion
```

Deletion candidates should include, if confirmed:

* production mock catalog behavior
* redundant mock flags
* stale deployment configs
* duplicate database helpers
* obsolete seed paths
* generated artifacts treated as canonical state
* dead services/classes
* obsolete documentation

Favor reducing total concepts.

---

# REQUIRED OUTPUT BEFORE IMPLEMENTATION

Stop after producing:

`docs/CODEBASE_AUDIT.md`

and present the proposed simplification plan.

Do not begin the large refactor automatically.

The document must end with:

# Recommended change sequence

Use small independently reversible phases.

Suggested structure:

```text
Phase 0 — Preserve working Pi and document rollback
Phase 1 — Remove silent mock fallback and expose DB failures
Phase 2 — Stop destructive automatic seeding
Phase 3 — Establish Neon as canonical database
Phase 4 — Point backend at canonical Neon
Phase 5 — Add minimal safe resource CRUD API
Phase 6 — Add minimal /admin/resources UI
Phase 7 — Remove obsolete mock/seed/deployment code
Phase 8 — Simplify schema only where justified
Phase 9 — Production verification
```

For each phase include:

```text
Goal
Files likely affected
Risk
Test
Rollback
Definition of done
```

---

# IMPLEMENTATION PHILOSOPHY

When implementation is later approved:

Prefer:

```text
delete 500 lines
```

over:

```text
add another abstraction to manage the existing 500 lines
```

Prefer:

```text
one obvious code path
```

over:

```text
feature flags selecting four code paths
```

Prefer:

```text
explicit failure
```

over:

```text
silent fallback
```

Prefer:

```text
deterministic behavior
```

over:

```text
randomness
```

Prefer:

```text
canonical database
```

over:

```text
generated copies of the same truth
```

Prefer:

```text
boring CRUD
```

over:

```text
clever content-management architecture
```

Prefer:

```text
reversible migration
```

over:

```text
big-bang rewrite
```

Do not introduce:

* Kubernetes
* Redis unless a demonstrated requirement exists
* event buses
* microservices
* GraphQL
* a new frontend framework
* a new authentication platform
* an ORM rewrite for aesthetic reasons
* speculative abstractions
* additional AI agents in the runtime
* automatic scraper complexity yet

This is a simplification project.

---

# FINAL QUESTIONS THE AUDIT MUST ANSWER

By the end I should be able to answer, confidently:

1. Where does every TalkBox get its resource data?
2. What is the single source of truth?
3. Why am I currently seeing `kiosk_mock_catalog.json` resources?
4. Can a broken database silently look healthy?
5. Can restarting a kiosk overwrite curated data?
6. Where exactly does the production database live today?
7. Is Neon currently being used, or merely supported by historical code?
8. How do I visually inspect the canonical database?
9. How does a nontechnical staff member safely edit a resource?
10. How do I add a new TalkBox without creating another database?
11. How do I update software without affecting resource data?
12. How do I recover if a deployment fails?
13. How do I recover if database data is accidentally changed?
14. Which 20% of the files explain 80% of the system?
15. What code can be deleted?
16. What is the smallest architecture capable of running TalkBox reliably in production?

Do not optimize for cleverness.

Optimize for my ability to understand, operate, repair, and safely expand this system.
