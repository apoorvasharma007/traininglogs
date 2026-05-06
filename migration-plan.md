# traininglogs 2.0 — docs sync, DB migration, E2E validation, and cutover

Tracks the end-to-end work required before `dev` merges to `main` as the 2.0 release.
Each phase is gated on explicit sign-off before the next begins.
Update the `▶ Resume here` pointer at the end of every work session.

---

## Context

- **Old DB** (`db`, port 5432): running, has 121 sessions in the **old schema** (missing
  `weight_unit`, `exercise_type`, `set_type`, unilateral columns, etc. added in the
  activity-support wave). This DB is the pre-migration reference — do not touch it.
- **New DB** (`db_validation`, port 5434): will receive a fresh schema application and
  full import of all 121 JSON sessions. This becomes the production DB after cutover.
- **JSON source of truth**: `output_training_logs_json/` — 121 files, already regenerated
  with the new schema during `chore/historical-data-regen`. These are what we import.
- **Session ID note**: old DB IDs are `YYYY-MM-DD_focus_N` (old scheme). New DB IDs are
  `YYYY-MM-DD-<sha256[:6]>` (new scheme). Cross-DB comparisons use **date** as the join
  key, not session ID. Column-level mismatches between old and new are **expected** — what
  must match are the core data values (weights, reps, sets, exercise names).

---

## Phase 1 — Documentation sync

All docs-only changes. No DB or app changes. Commit to `dev` before moving to Phase 2.

### 1.1 README.md

- [ ] Remove reference to `docs/architecture.md` (deleted in code-health pass).
- [ ] Replace old CLI example (`traininglogs log --phase N --week N`) with current
      syntax (`traininglogs log <file|dir>` and `traininglogs log --program <name> --phase N --week N`).
- [ ] Update input directory reference from `input_training_logs_md/` to `inputs/programs/<slug>/`.
- [ ] Add `traininglogs validate <file>` to the usage section.
- [ ] Verify Setup section still matches: venv install, `.env` setup, `docker compose up -d`.

### 1.2 CHANGELOG.md

- [ ] Consolidate all merged waves under `[Unreleased]` — remove "in progress" labels
      from `feature/inputs-restructure` and other already-shipped entries.
- [ ] Fix 1.0.0 entry: update stale filenames (`models_v2.py` → `models.py`,
      `insert_v2.py` → `insert.py`, `import_json_to_db_v2.py` → `import_sessions_to_db.py`,
      `processor_v2.py` → `processor.py`).
- [ ] Fix 1.0.0 "Notes" section: remove archived/ reference (files were deleted, not just archived).
- [ ] Ensure every merged branch/wave has a correctly-dated entry.
- [ ] Verify `[Unreleased]` compare link and `[1.0.0]` tag link at bottom are correct.

### 1.3 docs/design.html

- [ ] Read through each section — flag any references to old filenames or old CLI syntax.
- [ ] Confirm the data model section reflects the current schema (new columns, new field names).
- [ ] Confirm the dashboard section is still accurate.
- [ ] Update the eyebrow + footer date if any content changes.

### 1.4 Commit

```bash
git add README.md CHANGELOG.md docs/design.html
git commit -m "docs: sync README, CHANGELOG, design.html to current codebase state"
```

**Sign-off gate:** review diff together before committing.

---

## Phase 2 — Fresh migration to new DB (`db_validation`, port 5434)

### 2.1 Verify new DB is empty

```bash
docker exec traininglogs-db_validation-1 psql -U traininglogs -d traininglogs_validation \
  -c "SELECT COUNT(*) FROM sessions;" 2>&1
# expected: relation "sessions" does not exist (empty DB, no schema yet)
```

### 2.2 Run import against new DB

The import script calls `apply_schema()` first, which runs `schema.sql` with
`CREATE TABLE IF NOT EXISTS` — on an empty DB this creates all tables with the
current schema (all new columns included). Then imports all 121 JSON files.

```bash
cd /Users/apoorvasharma/Projects/traininglogs
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation \
  .venv/bin/python scripts/import_sessions_to_db.py
```

Expected output: `121 imported, 0 skipped, 0 failed.`

### 2.3 Verify new DB schema

```bash
docker exec traininglogs-db_validation-1 psql -U traininglogs -d traininglogs_validation \
  -c "\d sessions" -c "\d exercises" -c "\d working_sets"
```

Confirm presence of: `weight_unit` (sessions), `exercise_type` (exercises),
`set_type` / `duration_seconds` / `distance_meters` / `heart_rate_bpm` /
`left_reps_full` / `left_reps_partial` / `right_reps_full` / `right_reps_partial` /
`rest_seconds` (working_sets).

### 2.4 Verify new DB row counts

```bash
docker exec traininglogs-db_validation-1 psql -U traininglogs -d traininglogs_validation \
  -c "SELECT COUNT(*) FROM sessions;" \
  -c "SELECT COUNT(*) FROM exercises;" \
  -c "SELECT COUNT(*) FROM working_sets;"
```

Expected: 121 sessions. Exercise and working_set counts must match old DB exactly
(1009 exercises, 2469 working_sets — captured at start of this plan).

**Sign-off gate:** confirm counts and schema columns before Phase 3.

---

## Phase 3 — End-to-end validation against new DB

All commands use `VALIDATION_DATABASE_URL` (port 5434) as `DATABASE_URL` via env override.

### 3.1 Validate a real input file

```bash
.venv/bin/traininglogs validate \
  inputs/programs/bodybuilding_transformation_system/phase_3/week_11/push_hypertrophy_foundation_block.md
```

Expected: prints model summary, exits 0.

### 3.2 Dry-run the full pipeline

```bash
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation \
  .venv/bin/traininglogs log \
  inputs/programs/bodybuilding_transformation_system/phase_3/week_11/push_hypertrophy_foundation_block.md \
  --dry-run
```

Expected: prints parsed session, no DB write, no git commit.

### 3.3 Real insert (no commit)

Pick a file that does NOT already exist in the new DB (or note session ID for cleanup).

```bash
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation \
  .venv/bin/traininglogs log \
  inputs/programs/bodybuilding_transformation_system/phase_3/week_11/push_hypertrophy_foundation_block.md \
  --no-commit
```

Then verify in DB:
```bash
docker exec traininglogs-db_validation-1 psql -U traininglogs -d traininglogs_validation \
  -c "SELECT session_id, weight_unit FROM sessions ORDER BY date DESC LIMIT 3;" \
  -c "SELECT name, exercise_type FROM exercises WHERE session_id = (SELECT session_id FROM sessions ORDER BY date DESC LIMIT 1);" \
  -c "SELECT number, set_type, weight_kg, reps_full FROM working_sets WHERE exercise_id = (SELECT id FROM exercises ORDER BY id DESC LIMIT 1);"
```

Confirm: `weight_unit = 'kg'`, `exercise_type = 'strength'`, `set_type = 'strength'` populated.

### 3.4 API smoke test

In one terminal:
```bash
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation \
  .venv/bin/uvicorn traininglogs.api.app:app --reload
```

In another:
```bash
# list sessions
curl -s -H "X-Api-Key: <your-key>" http://localhost:8000/sessions | python3 -m json.tool | head -40

# single session (pick any session_id from the list output)
curl -s -H "X-Api-Key: <your-key>" http://localhost:8000/sessions/<session_id> | python3 -m json.tool | head -60

# exercise history
curl -s -H "X-Api-Key: <your-key>" "http://localhost:8000/exercises/Bench%20Press/history" | python3 -m json.tool | head -40
```

Confirm: all three endpoints return 200 with non-empty data.

### 3.5 Dashboard rebuild

```bash
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation \
  .venv/bin/python scripts/build_dashboard.py
```

Open `docs/index.html` in a browser. Confirm sections render with real data (not empty/zeroed).

**Sign-off gate:** walk through all validation steps together, confirm each output before Phase 4.

---

## Phase 4 — Side-by-side data comparison (old vs new)

Goal: confirm core row values are identical. Column mismatches are expected (old DB
is missing new columns). We compare on: date → exercises per session (by name and
order) → sets per exercise (weight_kg, reps_full, rpe).

### 4.1 Write and run comparison script

Create `scripts/compare_dbs.py` — connects to both DBs, joins on date, produces a
diff report:

```
OLD DB: postgresql://traininglogs:traininglogs@localhost:5432/traininglogs
NEW DB: postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation
```

Checks (in order):
1. **Session count**: both have 121 sessions. List any dates present in one but not the other.
2. **Exercise count per session** (joined by date): for each date, compare number of
   exercises. List any mismatches.
3. **Set count per exercise** (joined by date + exercise name + exercise number):
   compare working_set count. List mismatches.
4. **Core field values** (for matched sets, joined by date + exercise name + set number):
   compare `weight_kg`, `reps_full`, `rpe`. Report any non-zero delta.

Output: a pass/fail summary with detail on any mismatches.

### 4.2 Review comparison output

Expected: 121/121 sessions matched, 0 field value mismatches. Any mismatch is a
blocker — investigate before proceeding.

**Sign-off gate:** comparison must pass 100% before cutover.

---

## Phase 5 — Cutover

### 5.1 Stop the old `db` container

```bash
docker compose stop db
```

### 5.2 Update .env

Change `DATABASE_URL` from port 5432 to 5434:
```
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation
```

### 5.3 Smoke-test with real DATABASE_URL

```bash
.venv/bin/pytest tests/ -x -q
```

All 147 tests must pass. (Note: tests use `TEST_DATABASE_URL` on 5433, not `DATABASE_URL` —
but `DATABASE_URL` is what the app and scripts use. Confirm tests still pass on 5433.)

### 5.4 Rename the docker-compose service (in a follow-up PR)

After cutover is verified, clean up docker-compose.yml:
- Rename `db_validation` → `db`; update port from 5434 → 5432; rename volume.
- Remove the old `db` service and volume entirely.
- Update `.env` back to port 5432.

This is a separate clean-up commit — don't bundle with the cutover.

### 5.5 Delete old `db` volume

```bash
docker volume rm traininglogs_postgres_data
```

**Sign-off gate:** confirm tests pass and app works on the new DATABASE_URL before
deleting the old volume (irreversible).

> **Current state (2026-05-07):** Steps 5.1–5.3 complete. Old `db` container is stopped.
> Old volume (`traininglogs_postgres_data`) is intentionally left intact as a safety net.
> Delete it only when you're confident the cutover is stable. To restore the old DB if
> needed: `docker compose start db` and revert `.env` to port 5432.

---

## Phase 6 — Migration runbook (`docs/migration-runbook.md`)

Write a reusable document covering:

1. **When to use this runbook** — schema changes that add columns, major data reimports,
   cutover between DB instances.
2. **Prerequisites checklist** — JSON files are source of truth and verified, test suite
   is green, old DB row counts are captured.
3. **Step-by-step commands** — verbatim commands for: start target DB, apply schema,
   import, verify counts, verify schema, run comparison, cutover .env, smoke test,
   delete old volume.
4. **Comparison script usage** — how to run `scripts/compare_dbs.py`, what the output
   means, what a passing run looks like.
5. **Rollback** — if comparison fails: stop the new DB, revert `.env`, restart old DB.
   No data loss because old DB was never touched.
6. **Post-cutover cleanup** — docker-compose rename, old volume deletion, CHANGELOG entry.

Commit alongside the compare script.

---

## ▶ Resume here

**Cutover complete (2026-05-07). `DATABASE_URL` now points to `db_validation` (port 5434).
147 tests passing. Old `db` container stopped; old volume retained as safety net (see 5.5).**

Next options:
- Wave 5 (Supabase cloud DB sync) — needs design conversation first.
- Wave 6 (dashboard polish) — can start immediately.
- Deferred cleanup: docker-compose rename (5.4), old volume deletion (5.5), migration runbook (Phase 6).
