# Neon Migration Runbook

Target organization: `org-super-sunset-88688178`

Target project: `soft-hat-27629835`

The existing standalone Neon project named `talkbox` is now the canonical
TalkBox database. Fly FastAPI connects to it with the server-side `DB_URI`;
Vercel, browsers, and kiosks call FastAPI and never receive Neon credentials.

The migration described below is complete. Its import procedures are retained
only for disaster recovery and rehearsal against a disposable branch. Never
run them against the populated canonical database during an application deploy.

## Safety rules

- Back up and validate the current database before every migration attempt.
- Use a non-production Neon branch for the first rehearsal.
- Never place a Neon owner or migrator connection string in a kiosk `.env`.
- Never run `seed-agencies` or `--confirm-replace` during application
  startup.
- Never point catalog replacement commands at an existing curated database.
- Use direct connections only for deliberate platform migrations and imports.
- Configure only the Fly backend with the pooled Neon application connection.
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

6. Build routing vectors:

   ```sh
   DB_URI="$NEON_DIRECT_IMPORTER_URI" \
     COLLECTION_NAME=query_categories \
     python main.py seed-category-vectors
   ```

7. A future direct-resource semantic-search rehearsal may build a fresh,
   versioned collection from Neon agency rows. The current production database
   intentionally contains only category-routing vectors.

   ```sh
   # Future command only after the seeder reads canonical Neon agencies:
   DB_URI="$NEON_DIRECT_IMPORTER_URI" \
     AGENCY_COLLECTION_NAME=agency_catalog_v2 \
     python main.py seed-agency-vectors
   ```

8. Validate counts, null phone numbers, duplicate names/phones, vector model
   metadata, content hashes, and representative semantic searches.
9. Restart the API repeatedly and prove all counts and a deliberate test edit
   remain unchanged.
10. Delete the rehearsal branch only after results are recorded.

## Production cutover

1. Create and validate a fresh local PostgreSQL dump.
2. Create a Neon restore point or protected branch before import.
3. Apply the already-rehearsed migrations to the production branch.
4. Import and build category-routing vectors using the explicit commands above.
5. Configure Fly `DB_URI` with the pooled application credential.
6. Set `FSC_RESOURCE_SYNC_ENABLED=false`, `KIOSK_MOCK_QUERY=false`, and
   `TALKBOX_SEED_ADMIN=false`.
7. Do not configure importer or migrator credentials in Fly runtime secrets.
8. Verify liveness, canonical catalog counts, category-vector SQL queries,
   directory results, and Twilio webhooks.
9. Keep the Pi's local stack unchanged during the first central API soak test.
10. Cut one kiosk over first. Retain the known-good local image and database
   dump until online and offline snapshot behavior passes production testing.

## Collection rotation

`query_categories` currently routes requests to categories followed by SQL
lookup in canonical Neon. A future `agency_catalog_v2` may contain one document
per Neon agency for direct semantic retrieval. Keep the collections separate.

LangChain stores both collections in `langchain_pg_embedding`. The near-text
vector is in its `embedding` column, the embedded source text is in `document`,
and canonical `resource_id`, category, content version, model, and content hash
live in `cmetadata` JSONB. `collection_id` joins
`langchain_pg_collection.uuid`, whose `name` selects the active collection.

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