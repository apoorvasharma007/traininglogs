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
# Requires a running validation DB and REGEN_DATABASE_URL set
REGEN_DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation \
  .venv/bin/python scripts/regen_historical.py

# With --overwrite: truncates the validation DB first (safe for re-runs from scratch)
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

## repopulate_validation_db.py

**Purpose:** Truncate the validation DB and repopulate it by processing all `.md` files
in `inputs/` from scratch. Used when you need the validation DB to reflect the current
pipeline state (e.g., after a processor change, to prepare for E2E validation).

**Safety guard:** refuses to run if `DATABASE_URL` does not look like the validation DB
(must contain port 5434 or "validation").

```bash
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation \
  .venv/bin/python scripts/repopulate_validation_db.py
```

Also writes updated JSON to `output_training_logs_json/`. Use `regen_historical.py`
instead if you want safety isolation (output to a separate directory first).
