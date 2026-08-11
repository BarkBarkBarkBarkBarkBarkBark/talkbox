# ADR 0001: Standalone TalkBox Neon as Canonical Resource Source

## Context

TalkBox briefly used an authenticated FSC Resource Platform snapshot as the
preferred kiosk resource source, while its standalone Neon database remained a
parallel store for agencies, categories, users, and pgvector data. Maintaining
two authorities made runtime behavior and deployments difficult to reason about.

## Decision

The existing standalone Neon project named `talkbox` is the canonical data
store. FastAPI connects through the server-side `DB_URI` setting and provides
all browser, website, admin, and kiosk access. Clients never connect to Neon
directly.

The former FSC synchronization and snapshot implementation remains disabled as
rollback code. It is not a runtime authority. Startup must not migrate, seed,
truncate, import, or create an administrator unless an operator explicitly
requests the relevant operation.

## Data Flow

```text
TalkBox Neon -> Fly FastAPI -> Vercel website and TalkBox kiosks
```

Local development may use the same Neon database by setting `DB_URI`; an
explicit local database is allowed only when deliberately configured.

## Consequences

- `agencies` and `categories` in TalkBox Neon back kiosk search and browse.
- `query_categories` continues to route queries to SQL categories.
- CSV import and seed commands are manual maintenance tools, never startup work.
- Direct resource embeddings require a separate, versioned future collection.

## Security

- Neon credentials exist only in backend runtime secret storage.
- Vercel receives public `VITE_*` configuration only.
- Fly secrets and local ignored environment files must never be committed or
  printed.
- Admin writes remain authenticated and server-side.