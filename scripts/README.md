# Scripts

Operational scripts for maintaining the traininglogs system. These are not part of
the installable package — run them directly with `.venv/bin/python scripts/<name>.py`.

---

## build_dashboard.py

**Purpose:** Rebuild `docs/index.html` from the current database.

Run this whenever you want to refresh the dashboard without processing a new session.
The `traininglogs log` command calls this automatically after each insert.

```bash
.venv/bin/python scripts/build_dashboard.py
```

Reads from `DATABASE_URL`. Writes to `docs/index.html`.

---

## import_sessions_to_db.py

**Purpose:** Bulk-import all JSON session files from `output_training_logs_json/` into
the database. Safe to re-run — skips sessions that already exist by session ID.

Use `--overwrite` to truncate all tables and reimport from scratch (useful after a schema
migration or when switching to a fresh DB).

```bash
# Incremental import (skip existing)
.venv/bin/python scripts/import_sessions_to_db.py

# Full reimport from scratch
.venv/bin/python scripts/import_sessions_to_db.py --overwrite
```

Reads from `DATABASE_URL`. See `.claude/db-migration.md` for the full migration workflow.

---

## regen_historical.py

**Purpose:** Regenerate all historical JSON files by running the current processor pipeline
over every `.md` file in `inputs/`. Safety-isolated — writes to a new output directory,
never overwrites `output_training_logs_json/`.

Run this when a parser, processor, or model change affects how existing session data is
computed (field values, session ID scheme, output shape). Read `.claude/regen-historical.md`
before running.

```bash
# Requires an isolated target DB and REGEN_DATABASE_URL set
REGEN_DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5435/traininglogs_migration \
  .venv/bin/python scripts/regen_historical.py

# With --overwrite: truncates the target DB first (safe for re-runs from scratch)
REGEN_DATABASE_URL=... .venv/bin/python scripts/regen_historical.py --overwrite

# Custom output directory
REGEN_DATABASE_URL=... .venv/bin/python scripts/regen_historical.py \
  --output-dir output_training_logs_json_regen
```

After reviewing the output, manually swap directories:
```bash
mv output_training_logs_json output_training_logs_json_old
mv output_training_logs_json_regen output_training_logs_json
```

---

## regen_historical_ai.py

**Purpose:** Regenerate all historical session data through the AI ingest pipeline
(`capture` → `extract` → `confirm`) instead of the rules parser, producing a fresh dataset
to compare against `output_training_logs_json/`. Unlike `regen_historical.py`, this is
interactive — each session's card is shown for confirmation or correction, same as
`traininglogs log --parser ai` — so budget real time, not just money.

Safety-isolated the same way: never targets prod or the test DB, writes JSON to a
version-stamped directory (`output_training_logs_json_v{app version}/` by default), and
is resumable — a `.regen_progress.json` in the output directory tracks which files are
already confirmed, so re-running the same command skips them and picks up where you left
off.

```bash
# See file count and an order-of-magnitude cost estimate. No API calls, no DB writes.
.venv/bin/python scripts/regen_historical_ai.py --dry-run

# Real run against an isolated target DB. Stops before the next file once cumulative
# spend crosses --max-cost (default $10); re-run the same command to resume.
REGEN_DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_regen \
  .venv/bin/python scripts/regen_historical_ai.py --max-cost 10

# Try it on a handful of files first
REGEN_DATABASE_URL=... .venv/bin/python scripts/regen_historical_ai.py --limit 3
```

After a full run, follow `.claude/regen-historical.md`'s comparison and sign-off steps
before treating the new directory as anything but a side-by-side reference.

---

## repopulate_db.py

**Purpose:** Truncate the prod DB and repopulate it by processing all `.md` files
in `inputs/` from scratch. Used when you need the prod DB to reflect the current
pipeline state (e.g., after a processor change).

**Safety guard:** refuses to run if `DATABASE_URL` looks like the test DB (port 5433
or contains `traininglogs_test`).

```bash
.venv/bin/python scripts/repopulate_db.py
```

Also writes updated JSON to `output_training_logs_json/`. Use `regen_historical.py`
instead if you want safety isolation (output to a separate directory first).
