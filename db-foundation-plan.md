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
- [x] 3. Record the baseline on the existing databases: local dev, then staging, then production
  with a yes in the session. `0001_baseline.sql` is the old `schema.sql`, which only creates what's
  missing, so `scripts/migrate.py --apply` runs it and records it. Before each: the dry run, and a
  `pg_dump --schema-only` compared before and after, which must show only `schema_migrations` as
  new. Production also gets a backup to `backups/` first.
  - Local dev (2026-10-25): refused and rolled back, nothing changed (schema dump and counts
    identical: 134 sessions, 3,420 sets, 101 custom exercises). It carries the exercise library
    branch's schema (`exercises.movement` dropped), which the baseline's starter insert needs. It
    gets its record after step 4, when `0002_exercise_library.sql` exists, or from a fresh copy.
  - Reference: `traininglogs_baseline_ref` in the local Docker Postgres, built from `0001` alone.
    Compare with `pg_dump` 17 (`docker run postgres:17`), `--schema-only --schema=public
    --no-owner --no-privileges`, since staging and production run Postgres 17.
  - Staging (2026-10-25, read only): the dry run lists `0001` only. The layout matches the
    reference except `users.timezone`, which defaults to `'Asia/Kolkata'` there and `'UTC'` in the
    file (changed in `d5230f2`; the file only creates what's missing, so staging kept the old
    default). Fixing it is a new file, waiting on Apoorva. Staging holds test data, so the real
    rehearsal is a copy of production taken the same day.
  - Production (2026-10-25): was paused (Supabase `INACTIVE`); restored with Apoorva's yes. Read
    only: the dry run lists `0001` only, and the layout matches the reference exactly (it already
    defaults `users.timezone` to `'UTC'`, so only staging drifted).
  - Rehearsal (2026-10-25): production copied into local `traininglogs_prod_copy` (`pg_dump
    --schema=public`, restored without `SET transaction_timeout` and `CREATE SCHEMA public`, which
    the local Postgres 16 refuses). Row counts matched in all 16 tables. `migrate.py --apply` ran
    `0001`: the layout gained only `schema_migrations`, every count stayed the same (the starter
    insert is `ON CONFLICT (name) DO NOTHING`), and a second run did nothing.
  - Staging applied (2026-10-25, Apoorva's yes): counts unchanged but for one `schema_migrations`
    row; a second dry run lists nothing.
  - Production backup (2026-10-25):
    `~/Projects/traininglogs/backups/prod-before-schema-files-20261025-2128.sql`, all 16 tables.
    The apply was blocked by Claude Code's permission check, so Apoorva ran it.
  - Production applied (2026-10-25): counts unchanged but for one `schema_migrations` row; a
    second dry run lists nothing. Staging and production now record `0001`.
  - Later: staging's `users.timezone` default (`'Asia/Kolkata'`) differs from the file and
    production (`'UTC'`). A one-off fix on staging, or leave it; staging is test data.
- [x] 4. Merge `db/foundation` into `dev` (needs Apoorva's yes), then merge `dev` into
  `exercises/library`, where the library's own `schema.sql` changes (its step 3) become
  `0002_exercise_library.sql`.
  Merged into `dev` as PR #76 (`f7f9f6e`). `dev` merged into `exercises/library` as `0bc8cb6`,
  with `0002_exercise_library.sql`; the rehearsal is in `exercise-library-plan.md`, Resume here.
  Local dev gets its record from a fresh production copy when F1 needs it.

## ▶ Resume here

**2026-10-25.** F0 is done (steps 1 to 4). Next work is F1 in `exercise-library-plan.md`. Later:
staging's `users.timezone` default (step 3).
