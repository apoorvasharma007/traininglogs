# Historical data regeneration

## When to regen

Regen is needed when a change affects how existing session data is computed or stored:

- Processor or parser logic changes that alter field values (e.g. lbs→kg conversion, a renamed field, a new computed field)
- Session ID scheme changes (happened once: `YYYY-MM-DD_focus_N` → `YYYY-MM-DD-sha256[:6]`)
- Model changes that restructure JSON output shape (e.g. `working_sets` → `sets`, new discriminator fields)

Do NOT regen for additive schema changes that don't touch existing data (e.g. adding a new optional column with a sensible default).

Regen is always a **separate branch** (`chore/historical-data-regen`), never bundled with the feature that prompted it. Feature branches must be stable on `dev` first.

## Process (high-level)

1. Confirm feature + model changes are stable on `dev` and suite is green.
2. Start an isolated target DB — a new docker-compose service on a different port. Never use prod or test.
3. Run `scripts/regen_historical.py` to a **new output directory** (not overwriting live `output_training_logs_json/`). The script accepts `--output-dir` and `--db-url`.
4. Compare new JSON against old: structural changes (expected — document them) vs value changes (suspicious — block on these).
5. Sign off: 0 suspicious diffs. If any, investigate and fix before proceeding.
6. Swap: rename live dir to `_old`, rename new dir to live name.
7. Verify imports cleanly into target DB. Check row counts.
8. Run side-by-side DB comparison (see `db-migration.md`).
9. After full sign-off: delete old output dir and cut a cleanup commit.

## Key rules

- **JSON is the source of truth, not the DB.** The DB is always reconstructable from the JSON files. Never treat the DB as authoritative for historical data.
- Always regen to a fresh directory — never in-place. A failed or cancelled regen has zero consequences this way.
- Session IDs may change between regen runs. Always join comparisons on **date**, not session_id.
- All skipped tests that were gated on "unblocked by: chore/historical-data-regen" must be unskipped and pass before the regen branch merges.
- After the swap, run the full test suite against the new JSON. 0 failures, 0 skips.

## Commands

```bash
# Start isolated target DB (adjust docker-compose.yml to add a service if needed)
docker compose up -d db_validation

# Run regen (writes to output_training_logs_json_regen/ by default)
REGEN_DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation \
  .venv/bin/python scripts/regen_historical.py --overwrite

# After reviewing output, swap directories
mv output_training_logs_json output_training_logs_json_old
mv output_training_logs_json_regen output_training_logs_json

# Verify test suite
.venv/bin/pytest tests/ -q
```
