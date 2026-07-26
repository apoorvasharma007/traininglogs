# Testing guide

## Phase order — always follow this sequence

1. **Unit tests** — models, validators, pure parsing logic. No DB, no files.
2. **Integration tests** — parser + processor + DB insert, against the real test DB (Docker). Never mock the DB.
3. **E2E** — manual validation using real session files and the full `traininglogs log` pipeline.

Never jump to E2E without unit and integration tests green first.

## Automated test suite

```bash
# Both Postgres services must be running (db and db_test)
docker compose up -d
.venv/bin/pytest tests/ -q
```

Tests use `TEST_DATABASE_URL` (port 5433), never `DATABASE_URL` (prod). If the suite is green, it does not mean E2E is green — the CLI and dashboard must be validated manually.

## Fixtures

`tests/fixtures/` has two subdirectories. All dates use year 3000 to guarantee no collision
with real session IDs. See `tests/fixtures/README.md` for the full table.

**`tests/fixtures/valid/`** — sessions that should parse and insert cleanly:

| File | What it covers |
|---|---|
| `strength_session.md` | Minimal bilateral strength — one exercise, warmup, goal, RPE, rest |
| `activity_session.md` | Activity sets — duration, distance, heart rate |
| `unilateral_session.md` | Unilateral reps with partial reps per side |
| `push_long_session.md` | 10 exercises, myo-rep failure, bodyweight (0 kg), empty warmup sections |
| `lower_strength_session.md` | llp and statichold failure, progressive warmups, missing RPE on some sets |
| `deload_session.md` | Deload week (`Deload: Yes`), bodyweight pullups |

**`tests/fixtures/invalid/`** — sessions that should fail at a specific known stage:

| File | Expected failure |
|---|---|
| `missing_date.md` | `ValueError` — date missing from metadata |
| `malformed_set_line.md` | `ValueError` — set line doesn't match parser pattern |
| `rpe_out_of_range.md` | `ValidationError` — RPE 11 outside valid range |
| `malformed_goal.md` | `ValueError` — goal string can't be parsed |
| `missing_focus.md` | `ValueError` — focus missing from metadata |

**Adding fixtures:** when adding a new parser feature or validation rule, add a fixture that
exercises it. For valid: copy from a real input in `inputs/programs/`, change the date to
`3000-MM-DD`. For invalid: create a minimal file that triggers the specific failure.
Automated tests use `tmp_path` inline fixtures — these files are for `traininglogs validate`
and `traininglogs log --no-commit` E2E workflows only.

## E2E protocol for a new feature

Run through all three stages in order. Do not skip any.

**Stage 1 — Validate (no DB write, no git)**
```bash
traininglogs validate tests/fixtures/valid/<relevant_fixture>.md
# Expected: model summary printed, exit 0
```

**Stage 2 — Real insert (no git commit)**
```bash
traininglogs log tests/fixtures/valid/<relevant_fixture>.md --test --no-commit
# --test routes to TEST_DATABASE_URL only; never touches LOCAL_DATABASE_URL.
# Then verify in test DB:
docker exec traininglogs-db_test-1 psql -U traininglogs -d traininglogs_test \
  -c "SELECT session_id, date, weight_unit FROM sessions WHERE date > '2999-01-01' ORDER BY date DESC LIMIT 3;"
```
Check that the new fields you added are populated correctly.

**Stage 3 — API + dashboard**
```bash
# Start API
DATABASE_URL=... .venv/bin/uvicorn traininglogs.api.app:app --reload

# List sessions
curl -s -H "X-Api-Key: <key>" http://localhost:8000/sessions | python3 -m json.tool | head -20

# Full session detail
curl -s -H "X-Api-Key: <key>" http://localhost:8000/sessions/<session_id> | python3 -m json.tool

# Rebuild dashboard and open in browser
.venv/bin/python scripts/build_dashboard.py
open docs/index.html
```

## What automated tests don't cover (validate manually)

- Dashboard rendering quality and data accuracy
- Multi-session batch processing (`traininglogs log <dir>`)
- Visual regression on the dashboard HTML

## When a schema change breaks existing tests

Mark broken tests with `pytest.mark.skip` and a comment stating exactly what unblocks the skip:
```python
@pytest.mark.skip(reason="unblocked by: chore/historical-data-regen")
```
Never delete tests to make CI green. All skips must be resolved before merging to `main`.
