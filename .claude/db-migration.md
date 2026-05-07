# DB migration strategy

## When you need a validation DB

Not every schema change needs a full migration. Use this judgement:

- **Additive column with a safe default** (e.g. `ADD COLUMN weight_unit TEXT DEFAULT 'kg'`): can apply via ALTER TABLE in-place. Still verify counts after.
- **New columns + historical data reimport** (e.g. adding `set_type`, `exercise_type`, unilateral columns): use a validation DB + full reimport from JSON.
- **Session ID scheme change**: always use a validation DB. Old IDs can't be compared directly.
- **Any destructive change** (rename/drop column, change type): validation DB + reimport, no exceptions.

Rule of thumb: if you'd need to re-run `regen_historical.py` for the change, you need a validation DB.

## Process (high-level)

1. **Never touch the prod DB during migration.** Keep it running as the reference.
2. Add a `db_validation` service to `docker-compose.yml` on a new port (e.g. 5434). New volume.
3. Start the new DB: `docker compose up -d db_validation`
4. Run `scripts/import_sessions_to_db.py --overwrite` against the new DB URL. This calls `apply_schema()` first (creates all tables with current schema), then imports all JSON from `output_training_logs_json/`.
5. Verify schema: `\d sessions`, `\d working_sets`, `\d exercises` — confirm new columns are present.
6. Verify row counts match expectations (capture old DB counts before starting).
7. E2E validation on the new DB:
   - `traininglogs validate tests/fixtures/strength_session.md`
   - `traininglogs log tests/fixtures/strength_session.md --dry-run`
   - `traininglogs log tests/fixtures/strength_session.md --no-commit` + verify in DB
   - API smoke test: `GET /sessions`, `GET /sessions/{id}`, `GET /exercises/{name}/history`
   - Dashboard rebuild: `scripts/build_dashboard.py`, open `docs/index.html` in browser
8. Side-by-side comparison: write/run a script that joins both DBs on **date** (not session_id) and compares weights, reps, exercise names. Session IDs may differ — that's expected. Value mismatches are blockers.
9. Sign off on 100% match. Investigate any mismatch before proceeding.
10. Cutover: update `DATABASE_URL` in `.env` to the new DB's port.
11. Smoke test: run the full test suite. All tests must pass (tests use `TEST_DATABASE_URL`, not `DATABASE_URL`, so this is independent).
12. Cleanup commit (separate from cutover): rename service in `docker-compose.yml`, update port, rename volume reference.
13. Delete old DB volume only after the new DB has been in use and verified stable. Irreversible — don't rush.

## Key rules

- **JSON is source of truth.** The DB is always reconstructable. If something goes wrong, the old DB is still running and `.env` can be reverted in seconds.
- **Compare on date, not session_id.** IDs may change between migrations. Core values (weights, reps, exercise names, set counts) must match.
- **Column mismatches between old/new are expected** when adding new columns. Only value mismatches matter.
- **docker-compose.yml cleanup is a separate commit** after cutover is verified stable. Don't bundle cleanup with cutover.
- **Old volume is the safety net.** Delete it only when you're confident. The command is: `docker volume rm traininglogs_postgres_data` — but check the volume name with `docker volume ls` first.
- When feature branches are merged to `dev` over time, the validation DB accumulates schema fragments. A fresh reimport from JSON is always cleaner than patching in-place.

## Commands

```bash
# Start validation DB (after adding service to docker-compose.yml)
docker compose up -d db_validation

# Import all JSON into validation DB
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation \
  .venv/bin/python scripts/import_sessions_to_db.py --overwrite

# Verify schema
docker exec traininglogs-db_validation-1 psql -U traininglogs -d traininglogs_validation \
  -c "\d sessions" -c "\d exercises" -c "\d working_sets"

# Verify row counts
docker exec traininglogs-db_validation-1 psql -U traininglogs -d traininglogs_validation \
  -c "SELECT COUNT(*) FROM sessions;" \
  -c "SELECT COUNT(*) FROM exercises;" \
  -c "SELECT COUNT(*) FROM working_sets;"

# Cutover
# Edit .env: change DATABASE_URL port from old to new
# Then verify tests still pass
.venv/bin/pytest tests/ -q
```
