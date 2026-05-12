# DB migration strategy

## When you need a migration DB

Not every schema change needs a full migration. Use this judgement:

- **Additive column with a safe default** (e.g. `ADD COLUMN weight_unit TEXT DEFAULT 'kg'`): can apply via ALTER TABLE in-place. Still verify counts after.
- **New columns + historical data reimport** (e.g. adding `set_type`, `exercise_type`, unilateral columns): use a migration DB + full reimport from JSON.
- **Session ID scheme change**: always use a migration DB. Old IDs can't be compared directly.
- **Any destructive change** (rename/drop column, change type): migration DB + reimport, no exceptions.

Rule of thumb: if you'd need to re-run `regen_historical.py` for the change, you need a migration DB.

---

## The absolute rule on prod

**Never repopulate or truncate prod without explicit written approval from Apoorva in the same session.**

This applies even when all validation checks pass. The validation result must be shown, the plan summarised, and Apoorva must say "go ahead" (or equivalent) before any destructive command runs against `DATABASE_URL`. Approval from a prior session does not carry forward.

This rule was added after a session (2026-05-07) where `repopulate_db.py` was run against prod immediately after `validate_regen.py` passed, without pausing for approval. The counts happened to match and no data was lost, but the process was wrong.

---

## Regen process (source-of-truth: .md inputs)

Use this when session IDs change, the parser changes, or a clean-slate reimport from raw inputs is needed.

### Step 1 — Capture prod baseline before touching anything

```bash
docker exec -i traininglogs-db-1 psql -U traininglogs -d traininglogs \
  -c "SELECT
        (SELECT COUNT(*) FROM sessions)     AS sessions,
        (SELECT COUNT(*) FROM exercises)    AS exercises,
        (SELECT COUNT(*) FROM working_sets) AS working_sets,
        (SELECT COUNT(*) FROM warmup_sets)  AS warmup_sets;"
```

Record these numbers. They are the acceptance criteria for the regen.

### Step 2 — Add db_regen service (if not already present)

`docker-compose.yml` should have a `db_regen` service at port 5434. Add it if missing, then:

```bash
docker compose up -d db_regen
```

### Step 3 — Populate the regen DB from .md inputs

```bash
REGEN_DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_regen \
  .venv/bin/python scripts/repopulate_db.py --regen
```

This must report `N inserted, 0 failed`. Any failures mean corrupt or unparseable inputs — fix them before proceeding (get user approval for each input fix).

### Step 4 — Run strict validation

```bash
REGEN_DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_regen \
  .venv/bin/python scripts/validate_regen.py
```

`scripts/validate_regen.py` checks:
- **Exact count match** on sessions, exercises, working_sets, warmup_sets between regen DB and prod DB
- **10 random spot-checks**: parses each .md file live and compares exercise count and per-exercise set/warmup counts against the regen DB

All checks must show `[PASS]`. Any `[FAIL]` is a blocker.

### When schema changes cause expected count mismatches

If the new schema adds or removes rows (e.g. a new table, a column that caused previously-skipped records to now be stored), the strict count equality check will fail. This is expected and not a blocker on its own, but it requires manual validation:

1. Document which mismatches are expected and why (schema change rationale).
2. For each mismatch, manually verify at least 5 affected records in the regen DB against the source .md file.
3. Write a short summary of what changed and why it's correct.
4. Get explicit written approval from Apoorva before running against prod.

Schema-change mismatches are **never** auto-approved even if they look correct. The mismatch summary and manual spot-checks must be shown and approved before prod is touched.

### Step 5 — STOP. Show results. Wait for approval.

Show the full output of `validate_regen.py` to Apoorva. Do not proceed until she explicitly approves running against prod.

Only after hearing "go ahead" (or equivalent):

```bash
.venv/bin/python scripts/repopulate_db.py
```

### Step 6 — Apply any schema changes not covered by CREATE TABLE IF NOT EXISTS

`apply_schema()` uses `CREATE TABLE IF NOT EXISTS`, so it won't add new columns to existing tables. For additive changes to existing tables:

```bash
docker exec -i traininglogs-db-1 psql -U traininglogs -d traininglogs \
  -c "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();"
```

Run any such statements explicitly after repopulate and verify the column exists.

### Step 7 — Final prod count check

```bash
docker exec -i traininglogs-db-1 psql -U traininglogs -d traininglogs \
  -c "SELECT
        (SELECT COUNT(*) FROM sessions)     AS sessions,
        (SELECT COUNT(*) FROM exercises)    AS exercises,
        (SELECT COUNT(*) FROM working_sets) AS working_sets,
        (SELECT COUNT(*) FROM warmup_sets)  AS warmup_sets;"
```

Must match the baseline captured in Step 1 (or the expected new counts if schema changes caused intentional differences).

---

## Migration process (source-of-truth: JSON files)

Use this when adding new schema columns and importing from the existing JSON output, not from raw .md inputs.

1. **Never touch the prod DB during migration.** Keep it running as the reference.
2. Add a `db_migration` service to `docker-compose.yml` on a new port (e.g. 5435). New volume.
3. Start the new DB: `docker compose up -d db_migration`
4. Run `scripts/import_sessions_to_db.py --overwrite` against the new DB URL. This calls `apply_schema()` first (creates all tables with current schema), then imports all JSON from `output_training_logs_json/`.
5. Verify schema: `\d sessions`, `\d working_sets`, `\d exercises` — confirm new columns are present.
6. Verify row counts match expectations (capture old DB counts before starting).
7. E2E validation on the new DB:
   - `traininglogs validate tests/fixtures/valid/strength_session.md`
   - `traininglogs log tests/fixtures/valid/strength_session.md --no-commit` + verify in DB
   - API smoke test: `GET /sessions`, `GET /sessions/{id}`, `GET /exercises/{name}/history`
   - Dashboard rebuild: `scripts/build_dashboard.py`, open `docs/index.html` in browser
8. Side-by-side comparison: write/run a script that joins both DBs on **date** (not session_id) and compares weights, reps, exercise names. Session IDs may differ — that's expected. Value mismatches are blockers.
9. **Show results to Apoorva. Wait for explicit approval before cutover.**
10. Cutover: update `DATABASE_URL` in `.env` to the new DB's port.
11. Smoke test: run the full test suite. All tests must pass.
12. Cleanup commit (separate from cutover): rename service in `docker-compose.yml`, update port, rename volume reference.
13. Delete old DB volume only after the new DB has been in use and verified stable. Irreversible — don't rush.

---

## Key rules

- **JSON is source of truth for JSON-based migrations. .md inputs are source of truth for regen.**
- **Compare on date, not session_id.** IDs may change between migrations. Core values (weights, reps, exercise names, set counts) must match.
- **Column mismatches between old/new are expected** when adding new columns. Only value mismatches matter.
- **Schema-change count mismatches require manual review and explicit approval.** Never auto-proceed.
- **docker-compose.yml cleanup is a separate commit** after cutover is verified stable. Don't bundle cleanup with cutover.
- **Old volume is the safety net.** Delete it only when you're confident. Check the volume name with `docker volume ls` first — the command is irreversible.
- When feature branches are merged to `dev` over time, the migration DB accumulates schema fragments. A fresh reimport from JSON is always cleaner than patching in-place.

---

## Commands reference

```bash
# Capture prod baseline
docker exec -i traininglogs-db-1 psql -U traininglogs -d traininglogs \
  -c "SELECT (SELECT COUNT(*) FROM sessions) AS sessions,
             (SELECT COUNT(*) FROM exercises) AS exercises,
             (SELECT COUNT(*) FROM working_sets) AS working_sets,
             (SELECT COUNT(*) FROM warmup_sets) AS warmup_sets;"

# Start regen DB
docker compose up -d db_regen

# Populate regen DB from .md inputs
REGEN_DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_regen \
  .venv/bin/python scripts/repopulate_db.py --regen

# Validate regen DB vs prod (strict counts + 10 spot-checks)
REGEN_DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_regen \
  .venv/bin/python scripts/validate_regen.py

# --- STOP. Show results to Apoorva. Wait for "go ahead". ---

# Repopulate prod
.venv/bin/python scripts/repopulate_db.py

# Apply schema changes not covered by CREATE TABLE IF NOT EXISTS
docker exec -i traininglogs-db-1 psql -U traininglogs -d traininglogs \
  -c "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS <col> <type> DEFAULT <val>;"

# Start migration DB (JSON-based migration)
docker compose up -d db_migration

# Import all JSON into migration DB
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5435/traininglogs_migration \
  .venv/bin/python scripts/import_sessions_to_db.py --overwrite

# Verify schema on migration DB
docker exec traininglogs-db_migration-1 psql -U traininglogs -d traininglogs_migration \
  -c "\d sessions" -c "\d exercises" -c "\d working_sets"
```
