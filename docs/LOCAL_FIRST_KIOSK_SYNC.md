# Local-first community kiosk synchronization

## Status

Design only. The standalone TalkBox Neon project remains canonical, while
community kiosks continue using their local Postgres databases as the primary
runtime copy. Automatic propagation is not implemented yet.

## Target flow

```text
authenticated /admin
  -> Fly FastAPI
  -> canonical TalkBox Neon
  -> versioned public resource snapshot
  -> scoped kiosk pull
  -> validated staging tables
  -> atomic local Postgres replacement
  -> local kiosk search and Browse
```

## Required implementation

1. Add a monotonic catalog version changed by committed agency/category writes.
2. Build public snapshots on Fly directly from Neon. Include agencies,
   categories, `show_on_kiosk`, and callable fields; exclude users and secrets.
3. Reuse the existing scoped snapshot endpoints, client, validation, and
   last-known-good cache after removing FSC-specific naming.
4. On each kiosk, poll the version endpoint, download only changed snapshots,
   validate the complete payload, load staging tables, and swap in one
   transaction. A failed or empty update must preserve the previous catalog.
5. Expose last-success time, current version, stale/error state, and a manual
   refresh operation for technicians.
6. Roll out to one kiosk before enabling fleet-wide polling.

## Search behavior

The current kiosk category-vector and SQL path can remain pointed at local
Postgres after synchronization. Category vectors need rebuilding only when
category definitions change, not for ordinary agency content or visibility
edits.

OpenAI currently embeds each spoken query, so local Postgres does not make voice
search fully offline. A network outage should use a local lexical fallback and
the cached directory; full offline semantic parity would require a separate
local embedding model.

## Security

- Neon credentials stay on Fly and never reach kiosks.
- Give each kiosk a revocable, read-only snapshot credential.
- Snapshots contain only public resource/configuration fields.
- Sign or authenticate every snapshot response and never log credentials.
- Do not synchronize users, auth records, admin imports, audit data, or kiosk
  interaction events.
