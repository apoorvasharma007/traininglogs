# Database foundation plan (F0)

The database audit of 2026-10-25 (exercise-library-plan.md, branch `exercises/library-7-picker`)
found that the table layout holds up to 100,000 users, but two things don't. Schema changes have no
history: `schema.sql` is applied by hand, and nothing records which database has which change.
And the API shared a connection pool between threads that must not be shared. F0 fixes both
before F1 of the exercise library, which restructures tables and needs ordered migrations.

## Blast radius

- `src/traininglogs/api/app.py`: the connection pool (step 1).
- `src/traininglogs/db/schema.sql`, `src/traininglogs/db/db.py`, `tests/conftest.py`,
  `tests/test_progress_api.py`: how the schema gets applied (step 2).
- `.claude/rules/schema.md`, `.claude/skills/verify/SKILL.md`, `docs/architecture.md`: the rules
  and docs that describe applying the schema (step 2).
- Local dev, staging and production databases: each records that it already has the baseline
  (step 3).

## Steps

- [x] 1. Thread-safe pool (`db/foundation-1-pool`). `ThreadedConnectionPool`, and a request
  waits up to 10 seconds for a free connection, then answers 503. Squashed as `c71db5d`, suite
  758 passed, 0 failed, 0 skipped.
- [x] 2. Schema change files (`db/foundation-2-migrations`). Plain numbered SQL files and our own
  runner (`db.py`), no new library; staging and production are run by hand with
  `scripts/migrate.py` (agreed 2026-10-25). `schema.sql` became `migrations/0001_baseline.sql`.
  Suite 768 passed, 0 failed, 0 skipped, on an existing database and on a brand-new one.
- [ ] 3. Record the baseline on the existing databases: local dev, then staging, then production
  with a yes in the session. `0001_baseline.sql` is the old `schema.sql`, which only creates what's
  missing, so `scripts/migrate.py --apply` runs it and records it. Before each: the dry run, and a
  `pg_dump --schema-only` compared before and after, which must show only `schema_migrations` as
  new. Production also gets a backup to `backups/` first.
- [ ] 4. Merge `db/foundation` into `dev` (needs Apoorva's yes), then merge `dev` into
  `exercises/library`, where the library's own `schema.sql` changes (its step 3) become
  `0002_exercise_library.sql`.

## ▶ Resume here

**2026-10-25.** Steps 1 and 2 done on `db/foundation` (worktree `~/Projects/traininglogs-db`,
private test database `traininglogs_db_foundation`, not pushed). Next: step 3 on the local dev
database (`traininglogs_dev`, port 5433), then staging, then production with a yes.

Running the suite here: `export
TEST_DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_db_foundation`,
then `PYTHONPATH=src ~/Projects/traininglogs/.venv/bin/pytest tests/`.
