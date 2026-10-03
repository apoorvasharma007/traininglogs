# traininglogs 2.0 — migration plan

Tracks the docs sync, DB migration, E2E validation, and cutover required before
`dev` merges to `main` as the 2.0 release.

**All phases complete as of 2026-05-07.**

---

## Context

- **Current prod DB** (`db`, port 5432, database `traininglogs`): new schema,
  all 121 sessions imported with path-based session IDs (`YYYY-MM-DD-sha256[:6]`).
  All activity-support columns present (`weight_unit`, `exercise_type`, `set_type`,
  unilateral columns, etc.).
- **Test DB** (`db_test`, port 5433, database `traininglogs_test`): used by the
  test suite (`TEST_DATABASE_URL`). Never touch manually.
- **JSON source of truth**: `output_training_logs_json/` — 121 files regenerated
  with the new schema during `chore/historical-data-regen`.

The old DB (`traininglogs_postgres_data` volume) was stopped and retained as a
safety net. Delete when confident the new DB is stable:
```bash
docker volume rm traininglogs_postgres_data
```

---

## Phase 1 — Documentation sync ✓

Completed in commit `320f9f6` (docs sync) and `b975795` (v2.0.0 CHANGELOG).

- [x] README.md — CLI syntax updated, old dir references removed, validate added.
- [x] CHANGELOG.md — [Unreleased] promoted to [2.0.0], clean format, no branch names.
- [x] design.html — stale collision description, past-design hints, migration claim fixed.

---

## Phase 2 — Fresh migration to new DB ✓

Completed in commit `2bcc2d0`.

- [x] Schema applied to new DB via `apply_schema()`.
- [x] 121 JSON sessions imported: `121 imported, 0 skipped, 0 failed`.
- [x] Schema verified: all new columns present.
- [x] Row counts verified: 121 sessions, exercise + working_set counts matched.

---

## Phase 3 — E2E validation ✓

Completed in commit `2bcc2d0`.

- [x] `traininglogs validate` on real input file — exits 0.
- [x] `traininglogs log ... --dry-run` — parsed and printed, no DB write.
- [x] `traininglogs log ... --no-commit` — inserted to DB, verified columns.
- [x] API smoke test: all three endpoints returned 200 with data.
- [x] Dashboard rebuild: `scripts/build_dashboard.py` ran clean.

---

## Phase 4 — Side-by-side data comparison ✓

Completed in commit `2bcc2d0` via `scripts/compare_dbs.py`.

- [x] 121/121 sessions matched on date.
- [x] Exercise counts matched per session.
- [x] Set counts matched per exercise.
- [x] Core field values (weight_kg, reps_full, rpe): 0 mismatches.

---

## Phase 5 — Cutover ✓

Completed in commits `2bcc2d0` and `33c6710`.

- [x] Old `db` container stopped.
- [x] `.env` updated: `DATABASE_URL` points to new DB (now port 5432, `traininglogs`).
- [x] DB renamed from `traininglogs_validation` → `traininglogs`.
- [x] docker-compose.yml cleaned: `db_validation` → `db`, port 5434 → 5432.
- [x] Test suite: 147 passing (now 158 after standalone session fix).
- [ ] Old volume deletion — deferred until confident (see above).

---

## Phase 6 — Migration runbook

`docs/migration-runbook.md` exists with reusable step-by-step commands for future
schema changes. Reference it before any future migration.

---

## E2E test protocol (run before every merge to main)

These are the commands to run manually. All should complete without errors.

```bash
# 1. Validate fixture files
.venv/bin/traininglogs validate tests/fixtures/valid/strength_session.md
.venv/bin/traininglogs validate tests/fixtures/valid/activity_session.md
.venv/bin/traininglogs validate tests/fixtures/valid/unilateral_session.md
.venv/bin/traininglogs validate tests/fixtures/valid/standalone_session.md

# 2. Dry-run a real program session (no DB write, no git commit)
.venv/bin/traininglogs log \
  inputs/programs/bodybuilding_transformation_system/phase_3/week_11/push_hypertrophy_foundation_block.md \
  --dry-run

# 3. Dry-run a standalone session (no DB write)
# (add a standalone file to inputs/sessions/ when one exists)

# 4. Test suite
.venv/bin/pytest tests/ -q

# 5. Dashboard rebuild
.venv/bin/python scripts/build_dashboard.py
# then open docs/index.html in browser — verify data is present, not empty
```

---

## ▶ Resume here

**All phases complete. `dev` is ready to merge to `main` as v2.0.0 pending:**
- [ ] E2E protocol run and signed off.
- [ ] Group-based program context validation landed (`fix/program-context-validation`).
- [ ] Old volume (`traininglogs_postgres_data`) deleted when confident.
</content>
</invoke>