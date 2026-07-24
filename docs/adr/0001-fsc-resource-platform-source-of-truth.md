# ADR 0001: FSC Resource Platform as Canonical Resource Source

## Context

TalkBox previously treated locally seeded agency and Health Scout datasets as
runtime resource authorities. That required code, database, or kiosk updates
for ordinary directory changes and created independently editable copies.

## Decision

The FSC Resource Platform hosted on Replit, with its production Neon PostgreSQL
database, is the canonical source for TalkBox resource and directory data. FSC
staff edit that data through the platform CMS.

TalkBox consumes only the versioned, authenticated `/api/v1/talkbox/*` JSON API
through the FastAPI backend on Fly.io. The API is the integration contract; the
Neon schema is not. Neither kiosks nor ordinary TalkBox synchronization connect
directly to Neon.

Synchronization is restricted to published public/configuration data:

- organizations and services/resources
- explicitly approved service contacts
- announcements
- kiosk profiles and kiosk-specific content configuration

Users, participants, clients, submissions, authentication records, audit logs,
case data, and kiosk interaction events must never enter the resource snapshot.

## Data Flow

```text
FSC Staff CMS -> Replit Neon PostgreSQL -> Replit TalkBox API
              -> Fly FastAPI cache -> TalkBox kiosks
```

FastAPI checks `content_version`, validates complete snapshots with typed
models, and atomically replaces its in-memory last-known-good snapshot only
after successful validation. Temporary upstream failures do not replace valid
cached data or stop unrelated call handling.

## Consequences

- FSC staff can update one centrally managed directory without a TalkBox deploy.
- Hard-coded runtime resource lists and CSV imports are deprecated as authorities.
- TalkBox must synchronize, cache, expose sync status, and tolerate API outages.
- The Replit API may add harmless fields without breaking older TalkBox clients.
- The API must publish content versions and complete TalkBox bootstrap snapshots.
- A Fly restart currently requires a successful bootstrap before canonical data
  is available because the Fly cache is intentionally in memory.

## Security

- No database credential or FSC service API key is placed on a kiosk.
- The FSC API credential exists only on the Fly backend and is never logged.
- TalkBox has no canonical write path; writes remain a Staff CMS responsibility.
- Only active contacts explicitly marked `allow_talkbox_call=true` may enter the
  server-side callable-number path. A resource's ordinary display phone is not
  sufficient authorization.