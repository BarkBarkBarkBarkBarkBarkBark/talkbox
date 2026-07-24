# Neon Migration Runbook

Target organization: `org-super-sunset-88688178`

Target project: `soft-hat-27629835`

Neon is the canonical persistence layer owned by the FSC Resource Platform.
FSC staff update resource data through the Replit-hosted Staff CMS. Ordinary
TalkBox runtime synchronization uses the authenticated FSC TalkBox API, not a
raw Neon connection. Kiosks must never receive Neon credentials or the FSC API
service credential.

The direct database procedures below are retained only for one-time migration,
recovery, and platform-owner maintenance. They are not the normal TalkBox data
flow and must not be configured as the kiosk integration contract.

## Safety rules

- Back up and validate the current database before every migration attempt.
- Use a non-production Neon branch for the first rehearsal.
- Never place a Neon owner or migrator connection string in a kiosk `.env`.
- Never run `seed-agencies` or `--confirm-replace` during application
  startup.
- Never point catalog replacement commands at an existing curated database.
- Use direct connections only for deliberate platform migrations and imports.
- Do not configure Fly's ordinary resource synchronization against raw Neon.
- Treat CSV as one-time import input, not ongoing authority.

## Required roles

Create separate credentials in Neon:

| Role | Connection | Purpose |
| --- | --- | --- |
| Migrator | Direct | Alembic DDL and extension setup |
| Importer | Direct | Deliberate initial catalog import and vector build |
| Application | Pooled | Runtime reads, authentication, and future controlled CRUD |

The application role must not own the database, create extensions, truncate
tables, or alter schema. Keep migrator and importer credentials out of Fly's
runtime secrets after bootstrap.

## Current source baseline

Before migration, the physical Pi reported:

- 379 agencies
- 29 categories
- 30 category-routing vectors in `query_categories`
- Local database host `talkbox-postgres`

The packaged CSV also contains 379 agency rows across 29 categories. Recheck
these values immediately before export because the local database remains the
current authority until cutover.

## Rehearsal

1. Create a temporary Neon branch under the target project.
2. Export direct and pooled connection strings through local shell variables;
   do not write them to the repository or command history.
3. Run migrations with the direct migrator URI:

   ```sh
   DB_URI="$NEON_DIRECT_MIGRATOR_URI" python main.py migrate
   ```

4. Confirm `alembic_version`, `categories`, `agencies`, `users`, and the
   `vector` extension exist.
5. Import only into the empty rehearsal database:

   ```sh
   DB_URI="$NEON_DIRECT_IMPORTER_URI" \
     python main.py seed-agencies --confirm-replace
   ```

6. Build routing vectors and a fresh agency collection:

   ```sh
   DB_URI="$NEON_DIRECT_IMPORTER_URI" \
     COLLECTION_NAME=query_categories \
     python main.py seed-category-vectors

   DB_URI="$NEON_DIRECT_IMPORTER_URI" \
     AGENCY_COLLECTION_NAME=agency_catalog_v1 \
     python main.py seed-agency-vectors
   ```

7. Validate counts, null phone numbers, duplicate names/phones, vector model
   metadata, content hashes, and representative semantic searches.
8. Restart the API repeatedly and prove all counts and a deliberate test edit
   remain unchanged.
9. Delete the rehearsal branch only after results are recorded.

## Production cutover

1. Create and validate a fresh local PostgreSQL dump.
2. Create a Neon restore point or protected branch before import.
3. Apply the already-rehearsed migrations to the production branch.
4. Import and vectorize once using the explicit commands above.
5. Publish and validate the FSC `/api/v1/talkbox/version` and `/bootstrap`
   endpoints against the curated production data.
6. Do not configure importer or migrator credentials in Fly runtime secrets.
7. Configure Fly with `FSC_RESOURCE_API_BASE_URL` and the
   `FSC_RESOURCE_API_KEY` secret, then verify liveness, sync status, catalog
   counts, query provenance, and Twilio webhooks.
8. Keep the Pi's local stack unchanged during the first central API soak test.
9. Cut one kiosk over first. Retain the known-good local image and database
   dump until online and offline snapshot behavior passes production testing.

## Collection rotation

`query_categories` routes requests to needs. `agency_catalog_v1` contains
agency facts for semantic retrieval. They are intentionally separate.

Agency vector generation refuses a nonempty target collection. When catalog
content or the embedding model changes:

1. Choose a new name such as `agency_catalog_v2`.
2. Build it without modifying the active collection.
3. Validate counts, dimensions, model metadata, hashes, and search fixtures.
4. Switch the reader configuration deliberately.
5. Retain the prior collection through the rollback window.

## Rollback

- Before kiosk cutover: point Fly back to the prior database/branch.
- During one-kiosk rollout: restore that kiosk's prior API configuration and
  image; its local Postgres volume remains untouched.
- For bad canonical data: restore the protected Neon branch or validated dump,
  then compare row counts and checksums before reopening writes.
- Never attempt rollback by rerunning the destructive CSV importer over a
  curated database.