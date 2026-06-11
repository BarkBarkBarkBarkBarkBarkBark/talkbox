# `scripts/`

One-shot operational tools. They live outside the backend image on purpose:
they carry heavy optional dependencies (e.g. `pandas`) that the running
service doesn't need, and they're invoked manually, not at startup.

All scripts are self-contained: they declare their dependencies inline via
[PEP 723](https://peps.python.org/pep-0723/), so `uv` resolves an ephemeral
venv per run — nothing to install globally.

## `rebuild_healthscout_db.py`

Rebuilds the Healthscout SQLite file that the backend consumes at
`/data/sacramento.db` from the upstream `HealthScout_*.csv` dump.

### When to run

Only when a fresher CSV dump arrives. The existing `database/sacramento.db`
is already loaded with 17 k Sacramento rows; `docker compose up` does **not**
invoke this script.

### How to run

```bash
# from the repo root
uv run scripts/rebuild_healthscout_db.py \
    --csv  csv/healthscout_providers.csv \
    --out  database/sacramento.db
```

### What it does

1. Reads the CSV (`pandas`, `low_memory=False`).
2. Renames `X/Y → longitude/latitude`.
3. Normalizes column names (lowercase + underscore).
4. Uppercases every text column, strips whitespace.
5. Standardizes phone numbers to `1-XXX-XXX-XXXX`.
6. Drops rows with missing `telephone_number`.
7. Writes the DataFrame into the `sacramento` table (`if_exists="replace"`)
   and creates an index on `(managedcareplan, pri_spec)` to match the hot
   query pattern.

The output path is the bind-mount source used by `docker-compose.yml`.

### After a rebuild

The backend bind-mounts the file **read-only**, so the container keeps a
stale SQLite handle. Restart the container to pick up the new file:

```bash
sudo docker restart talkbox-backend
```
