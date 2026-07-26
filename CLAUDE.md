# traininglogs

## Vision

A personal training log system where you describe your workout in natural language, an AI agent maps it to a strict structured schema, stores it in a database, and serves it to a dashboard on your website.

Capture happens offline during the workout (draft saved locally in a PWA). Processing happens post-workout — AI maps the draft to the schema, asks clarifying questions if needed, then saves to DB.

---

## Active plans

No active plans. Completed plans are archived in `archived/`.

---

## Deferred design decisions

**Exercise type inference (input UX)**

Currently the user must write `exercise_type: activity` explicitly in the markdown, and the parser routes to the right set parser based on it. Deferred decision: infer the exercise/set type from the content of the set line itself (e.g. `min`, `km`, `HR` signals → ActivitySet; `kg x reps` → StrengthSet) so the user never has to specify a type. LLM-assisted classification and an exercise registry are also options. Keep `exercise_type` as an explicit override escape hatch. Revisit when touching the input format or parser next.

---

## Operational guides

Read these before any significant development work. They capture lessons from building
against `dev` with multiple feature branches.

| Guide | When to read |
|---|---|
| [`.claude/regen-historical.md`](.claude/regen-historical.md) | Before any schema, parser, or session-ID change that affects existing data |
| [`.claude/db-migration.md`](.claude/db-migration.md) | Before adding columns, changing schema, or cutting over to a new DB |
| [`.claude/testing-guide.md`](.claude/testing-guide.md) | Before writing tests or doing E2E validation for a new feature |
| [`.claude/migration-plan.md`](.claude/migration-plan.md) | 2.0 migration tracking doc — all phases complete; contains E2E test protocol |

---

## Source of truth

Don't duplicate what these documents already say. Link to them.

| Topic | Lives in |
|---|---|
| System shape, data model, decisions, dashboard design, what's next | [`docs/design.html`](docs/design.html) |
| Released changes, per-version state, validation rules in effect | [`CHANGELOG.md`](CHANGELOG.md) |
| How to install and run the app | [`README.md`](README.md) |
| Agent working rules (this file) | `CLAUDE.md` |

`docs/index.html` is the **published dashboard**, not documentation. It is rebuilt by `scripts/build_dashboard.py` (called automatically by `traininglogs log`) — never hand-edit it.

---

## Docs hygiene (read before opening a PR)

**On every PR that changes app behavior:**

- Add an entry under `## [Unreleased]` in `CHANGELOG.md` (Added / Changed / Fixed / Removed). Don't ship behavior without a changelog line.
- If the system shape, data model, API contract, storage layout, or dashboard design changes → update `docs/design.html` in the same PR and bump the eyebrow + footer date manually.
- The app-version stamp inside `design.html` (`<span class="app-version">…</span>`) is auto-synced by CI on merge to `main`. **Do not edit it by hand.**
- If validation rules change → update both the data-model section in `design.html` and the "Validation rules in effect" block in the relevant CHANGELOG entry.

**On cutting a release** (bump `pyproject.toml` `version`):

- Move `[Unreleased]` entries under a new `## [X.Y.Z] - YYYY-MM-DD` heading in `CHANGELOG.md`.
- Add the `[X.Y.Z]` compare/tag link at the bottom of the file.
- Push to `main`. CI handles tagging, the GitHub release, and the `design.html` version stamp.

**Never:**

- Hand-edit `docs/index.html` (regenerate via `traininglogs log`).
- Add architecture or "current state" narrative to this file — it belongs in `design.html` or `CHANGELOG.md`.

---

## Branching

```
main  ←  stable, releases cut from here
  └── dev  ←  integration branch for all new work
        └── feature/<name>, fix/<name>, chore/<name>
```

- `main` is always stable. Never commit directly to `main` during new development.
- All feature branches cut from `dev`, merged back to `dev`.
- `dev` merges to `main` only when the new version is production-ready.
- One feature or fix per branch. Squash merge to keep history clean.

## Commits

- Small, atomic commits. Each commit leaves the codebase working.
- Format: `<type>: <short description>` — types: `feat`, `fix`, `test`, `refactor`, `chore`, `docs`.
- No unrelated changes bundled in one commit.

## Testing

### Phase order — always follow this sequence

1. **Unit tests first.** Model, validation, and pure-logic changes get unit tests before any pipeline code is touched. Run them green before proceeding to the next phase.
2. **Integration tests second.** Parser, processor, and DB insert changes get integration tests against a real test DB (Docker). Never mock the DB.
3. **E2E last.** Manual validation using `traininglogs validate` (no DB write) and `traininglogs log --no-commit` (DB write, no git) against files in `tests/fixtures/` before opening a PR. See [`.claude/testing-guide.md`](.claude/testing-guide.md) for the full protocol.

### Breaking changes

- When a field rename, schema change, or model restructure breaks existing tests, mark them `pytest.mark.skip` with a comment stating exactly what unblocks the skip (e.g., `"unblocked by: historical data regen in chore/historical-data-regen"`).
- Never delete a test to make CI green. Skip with a reason.
- All skips must be resolved before merging to `main`.
- Historical data regeneration is a separate branch (`chore/historical-data-regen`) after model + parser are stable on `dev`. It is not part of any feature branch.

### Feature checklist — required before opening a PR

- [ ] Every new model class has unit tests for: valid construction, each validator (valid + rejection cases), and `model_dump(mode="json")` round-trip.
- [ ] Every new discriminated union has dispatch tests for each variant.
- [ ] Every changed field that becomes Optional has a test confirming `None` is accepted and an empty string is still rejected.
- [ ] Existing tests pass or are explicitly skipped with a reason.
- [ ] `pytest tests/` runs clean locally (skips are fine, failures are not).
- [ ] CHANGELOG.md has an entry under `[Unreleased]`.
- [ ] If schema or API contract changed: `docs/design.html` updated in the same PR.

### Test fixtures

- Sample session files live in `tests/fixtures/` — three canonical inputs covering strength, activity, and unilateral sessions. Use these for E2E validation.
- New feature tests create their own in-code fixtures or sample JSON using the new schema. Do not modify existing output JSON files during feature development.
- Existing JSON in `output_training_logs_json/` is historical data — treated as read-only until `chore/historical-data-regen` runs.
- DB tests use a real Postgres test DB via Docker Compose. Never mocks.
- See [`.claude/testing-guide.md`](.claude/testing-guide.md) for the full E2E protocol.

## Working conventions

- Python 3.10+, PEP 8, type hints on all functions.
- No unnecessary abstractions — solve the current problem only.
- No ORM unless there's a real pain point that justifies one.
- Don't change DB column or Pydantic field names without explicit instruction — the schema, API, and dashboard depend on them.
- Validation errors raise `TrainingLogValidationError`.
- `.env` for secrets (never committed); `.env.example` documents required vars.

## Commands

```bash
# Install (always use the project venv)
.venv/bin/pip install -e .

# Run tests (requires docker compose up -d)
.venv/bin/pytest tests/

# Start all Postgres services (prod, test, validation)
docker compose up -d
```

### traininglogs CLI

```bash
# Process a single session file
traininglogs log inputs/programs/<slug>/phase_N/week_N/<session>.md

# Process all sessions in a directory
traininglogs log inputs/programs/<slug>/phase_N/week_N/

# Process a week by program/phase/week flags
traininglogs log --program <slug> --phase N --week N

# Validate a file without writing to DB (exit non-zero on failure)
traininglogs validate inputs/programs/<slug>/phase_N/week_N/<session>.md
traininglogs validate tests/fixtures/strength_session.md   # quick smoke test

# Flags (work with any invocation form)
traininglogs log <target> --no-commit     # insert to DB, skip git commit
traininglogs log <target> --pr            # insert, commit, open a PR

# Start the API server
uvicorn traininglogs.api.app:app --reload
# API at http://localhost:8000 — all requests require X-Api-Key header
```

### Scripts

See `scripts/README.md` for full details on each script.

```bash
# Rebuild the dashboard HTML from the current DB
.venv/bin/python scripts/build_dashboard.py

# Bulk-import all JSON session files into the current DB (idempotent)
.venv/bin/python scripts/import_sessions_to_db.py
.venv/bin/python scripts/import_sessions_to_db.py --overwrite   # truncate first

# Regenerate all historical JSON from the current processor pipeline
# (safety-isolated — writes to a fresh dir, not output_training_logs_json/)
# See .claude/regen-historical.md before running
REGEN_DATABASE_URL=<validation-db-url> .venv/bin/python scripts/regen_historical.py

# Truncate and repopulate the prod DB from current .md inputs
# Script refuses to run if DATABASE_URL looks like the test DB
.venv/bin/python scripts/repopulate_db.py
```
