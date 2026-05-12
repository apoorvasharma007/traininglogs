# DB Migration Runbook

A reusable step-by-step guide for migrating the traininglogs database to a new schema.
Use this whenever a schema change requires a full reimport rather than in-place ALTER TABLE.

For the strategic context behind these steps, see `.claude/db-migration.md`.

---

## When to use this runbook

- New columns added that require historical data to be recomputed (not just `DEFAULT`-backfilled)
- Session ID scheme changed
- Field renames or type changes in the Pydantic model or DB schema

Do NOT use this for simple additive columns with safe defaults — those can be applied with
`ALTER TABLE` directly after confirming no data is affected.

---

## Prerequisites

Before starting:

- [ ] Feature branches merged to `dev`, suite fully green (0 skipped, 0 failed)
- [ ] Historical JSON in `output_training_logs_json/` is up to date (run `regen_historical.py` first if needed)
- [ ] Old DB row counts captured: sessions, exercises, working_sets
- [ ] Old DB is running and reachable — do not touch it during migration

Capture old counts:
```bash
docker exec traininglogs-db-1 psql -U traininglogs -d traininglogs \
  -c "SELECT COUNT(*) FROM sessions;" \
  -c "SELECT COUNT(*) FROM exercises;" \
  -c "SELECT COUNT(*) FROM working_sets;"
```

---

## Step 1 — Start isolated target DB

Add a `db_migration` service to `docker-compose.yml` (different port, new volume):

```yaml
db_migration:
  image: postgres:16
  environment:
    POSTGRES_DB: traininglogs_migration
    POSTGRES_USER: traininglogs
    POSTGRES_PASSWORD: traininglogs
  ports:
    - "5435:5432"
  volumes:
    - postgres_migration_data:/var/lib/postgresql/data
```

```bash
docker compose up -d db_migration
```

---

## Step 2 — Import all JSON into target DB

`import_sessions_to_db.py` calls `apply_schema()` first, which creates all tables
with the current schema (new columns included).

```bash
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5435/traininglogs_migration \
  .venv/bin/python scripts/import_sessions_to_db.py --overwrite
```

Expected: `N imported, 0 skipped, 0 failed.`

---

## Step 3 — Verify schema and row counts

```bash
docker exec traininglogs-db_migration-1 psql -U traininglogs -d traininglogs_migration \
  -c "\d sessions" -c "\d exercises" -c "\d working_sets"
```

Confirm all new columns are present. Then verify counts match what you captured in prerequisites:

```bash
docker exec traininglogs-db_migration-1 psql -U traininglogs -d traininglogs_migration \
  -c "SELECT COUNT(*) FROM sessions;" \
  -c "SELECT COUNT(*) FROM exercises;" \
  -c "SELECT COUNT(*) FROM working_sets;"
```

---

## Step 4 — E2E validation on the target DB

```bash
# Validate a fixture file (no DB write, no git)
traininglogs validate tests/fixtures/valid/strength_session.md

# Real insert (no commit) — check that new fields populate correctly
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5435/traininglogs_migration \
  traininglogs log tests/fixtures/valid/strength_session.md --no-commit

# Confirm in DB
docker exec traininglogs-db_migration-1 psql -U traininglogs -d traininglogs_migration \
  -c "SELECT session_id, date FROM sessions ORDER BY date DESC LIMIT 3;"

# API smoke test (in one terminal start the server, in another run curls)
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5435/traininglogs_migration \
  .venv/bin/uvicorn traininglogs.api.app:app --reload --port 8001

curl -s -H "X-Api-Key: $API_KEY" http://localhost:8001/sessions | python3 -m json.tool | head -20
curl -s -H "X-Api-Key: $API_KEY" "http://localhost:8001/exercises/Bench%20Press/history" | python3 -m json.tool | head -20

# Dashboard rebuild
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5435/traininglogs_migration \
  .venv/bin/python scripts/build_dashboard.py
open docs/index.html
```

**Sign-off gate:** confirm each output before proceeding. Any missing data or error is a blocker.

---

## Step 5 — Side-by-side comparison (old vs new)

Write (or reuse) a comparison script that joins both DBs on **date** and checks:

1. Session count matches
2. Exercise count per session matches (joined by date)
3. Set count per exercise matches (joined by date + exercise name)
4. Core field values match: `weight_kg`, `reps_full`, `rpe`

Compare on date, not session_id — IDs may have changed. Column mismatches from new
columns are expected; value mismatches are blockers.

**Sign-off gate:** 100% match before cutover. Any mismatch must be investigated.

---

## Step 6 — Cutover

Update `.env`:
```
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5435/traininglogs_migration
```

Run the full test suite to confirm nothing broke (tests use `TEST_DATABASE_URL`, not
`DATABASE_URL`, so this is an independent check):
```bash
.venv/bin/pytest tests/ -q
```

All tests must pass.

---

## Step 7 — Cleanup (separate commit, after cutover is stable)

In `docker-compose.yml`:
- Remove the old `db` service entry
- Rename `db_migration` → `db`
- Update port to 5432

Update `.env.example` to reflect the new port and DB name.

Delete the old DB volume **only after the new DB has been in production use and verified**:
```bash
docker volume ls                          # confirm the volume name
docker volume rm traininglogs_<old-name>  # irreversible
```

Remove the `db_migration` service from `docker-compose.yml` and the corresponding volume
from the `volumes:` section once the cleanup commit is merged.

---

## Rollback

If anything goes wrong before cutover:
1. Revert `.env` to the old DB URL
2. `docker compose start db` (if stopped)
3. Old data is untouched — the old DB was never modified

If anything goes wrong after cutover but before old volume deletion:
1. Revert `.env` to the old DB URL and port
2. Restart old container
3. Root-cause before retrying
