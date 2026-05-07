# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2026-05-07

### Added

- `inputs/` directory layout: `inputs/programs/<slug>/phase_N/week_N/` for program
  sessions; `inputs/sessions/` for standalone workouts not tied to a program.
- `tests/fixtures/` with three canonical fixture files: `strength_session.md`,
  `activity_session.md`, `unilateral_session.md`.
- `traininglogs validate <file>` subcommand — parses and validates a session file,
  prints a model summary, exits non-zero on failure. No DB write.
- `ActivitySet` model and `### Activity Sets` markdown header. Supports any
  combination of `duration_seconds`, `distance_meters`, `heart_rate_bpm`.
- Unilateral rep support on `StrengthSet` via `left`/`right` keywords; partial
  reps (`left 8 + 1`) map to `{full, partial}` per side.
- `Rest(BaseModel)` with `minutes` and `seconds` fields; validators reject both
  being set simultaneously.
- `AnySet` discriminated union (`StrengthSet | ActivitySet`) on `set_type`.
- `weight_unit: Literal["kg", "lbs"] = "kg"` on `TrainingSession`; lbs→kg
  conversion runs at parse time.
- `exercise_type TEXT NOT NULL DEFAULT 'strength'` on `exercises` table.
- `set_type`, `duration_seconds`, `distance_meters`, `heart_rate_bpm`,
  `left_reps_full`, `left_reps_partial`, `right_reps_full`, `right_reps_partial`,
  `rest_seconds` columns on `working_sets` table.
- `weight_unit TEXT NOT NULL DEFAULT 'kg'` on `sessions` table.
- 15 unit tests in `tests/test_parse.py` covering error paths and happy paths for
  `_parse_goal`, `_parse_warmup_set_line`, `_parse_working_set_line`, and
  `build_training_session`.

### Changed

- **Session ID scheme** — `YYYY-MM-DD_focus_N` replaced by
  `YYYY-MM-DD-<sha256[:6] of path relative to inputs/>`. Deterministic: same file
  path always produces the same ID.
- `traininglogs log` accepts a positional `<file>` or `<dir>`, or
  `--program <slug> --phase N --week N` to resolve to
  `inputs/programs/<slug>/phase_N/week_N/`. Old `--phase`/`--week` required args
  removed.
- `parse.py` now returns plain dicts shaped directly for `model_validate()`. No
  intermediate dataclass layer.
- `processor.py` pipeline: parse → inject `session_id` → lbs conversion →
  `model_validate()`. No bridge step.
- `Exercise.working_sets` renamed to `sets`. API response key `working_sets`
  renamed to `sets`.
- `Goal.rest_minutes` replaced by `rest: Optional[Rest]`.
- Module renames: `models_v2`→`models`, `insert_v2`→`insert`,
  `processor_v2`→`processor`. Script renames: `regen_v2`→`regen_historical`,
  `compare_v2`→`compare_sessions`, `import_json_to_db_v2`→`import_sessions_to_db`.
- `inputs/` replaces `input_training_logs_md/` as the working inputs directory.
  121 historical session files migrated.
- All 121 historical JSON snapshots regenerated with the new pipeline (path-based
  session IDs, `sets` key, `set_type` discriminator, `Rest` goal field).

### Fixed

- `_parse_working_set_line`, `_parse_warmup_set_line`, `_parse_goal`,
  `build_training_session` — silently returned `None` on malformed input; now raise
  `ValueError` with the offending content.
- `processor.py`: `Goal.rest_minutes` was not mapped to `Goal.rest` — `goal_rest_min`
  was stored as NULL for every session.
- 27 input files with invalid formats corrected: single rep count (`10 reps` instead
  of `10-12 reps`), `+` suffix on goal weights, explicit `kg` unit in warmup lines,
  bare-number warmup line.
- `fetch.py`: `get_sessions()` and `get_session()` now select all new columns;
  result key renamed `working_sets`→`sets`.

### Removed

- `models_dataclass.py` — legacy parallel dataclass layer.
- Old `--phase`/`--week` as standalone required args (replaced by the
  `--program/--phase/--week` combination or a positional target).
- `docs/architecture.md` — content subsumed by `docs/design.html`.

### Validation rules in effect

- `failure_technique` is only valid on sets where `rpe == 10`.
- Exercise `number` fields must be sequential starting at 1.
- `week` must be between 1 and `program_length_weeks` (when program context is present).
- RPE must be a whole or half step between 1 and 10.
- `rest.minutes` must be 0–15; `rest.seconds` must be 0–900; both cannot be set simultaneously.
- Required string fields reject empty or whitespace-only values.

---

## [1.0.0] - 2026-05-05

Initial tagged release. Seed entry — describes the system as it stands at v1.0.0.

### Added

- **Pydantic v2 data model** (`models/models.py`) as the canonical schema.
  Root type `TrainingSession` with nested `Exercise`, `WorkingSet`, `WarmupSet`,
  `Goal`, `RepRange`, `RepCount`, and a `FailureTechnique` discriminated union
  covering myo-reps, lengthened-partials, static holds, and drop sets.
- **Markdown parser** (`parser/extract.py`, `parser/parse.py`) — rule-based,
  deterministic, no LLM in the hot path.
- **Processor CLI** (`processor/processor.py`) — DB-first, JSON-second.
  Errors on `session_id` collision rather than silently overwriting.
- **PostgreSQL storage** with four tables: `sessions`, `exercises`,
  `working_sets`, `warmup_sets`. Cascading deletes on `session_id`.
  `failure_technique` stored as JSONB matching the discriminated union shape.
- **JSON snapshots** written to `output_training_logs_json/` after every DB
  insert, derived from `session.model_dump(mode="json")`.
- **FastAPI REST API** (`api/app.py`) with `X-Api-Key` auth (fails at startup
  if `API_KEY` is unset). Three endpoints:
  - `GET /sessions` — list, filterable by phase, week, and date range.
  - `GET /sessions/{session_id}` — full session detail.
  - `GET /exercises/{name}/history` — per-exercise working-set history.
- **Static dashboard** (`cli/dashboard.py`) — single HTML file with inline
  JSON and Chart.js, rendered into the nine-section "Training Almanac" layout.
  Built from 11 SQL aggregations in `analytics/queries.py`.
- **`traininglogs log` workflow** (`cli/log.py`) — parses a phase/week of
  markdown, inserts to DB, writes JSON snapshots, commits, rebuilds the
  dashboard, and (with `--publish`) pushes the dashboard to the website repo.
- **Test suite** — real Postgres test DB via Docker (no DB mocks), pytest.
- **CI** — GitHub Actions runs the test suite on push and PR.
- **Technical design doc** at `docs/design.html`.

### Validation rules in effect

- `failure_technique` is only valid on working sets where `rpe == 10`.
- Exercise `number` fields must be sequential starting at 1.
- `week` must be between 1 and `program_length_weeks`.
- RPE must be a whole or half step between 1 and 10.
- `rest_minutes` and `actual_rest_minutes` must be between 0 and 15.
- Required string fields reject empty or whitespace-only values.

[Unreleased]: https://github.com/apoorvasharma007/traininglogs/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/apoorvasharma007/traininglogs/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/apoorvasharma007/traininglogs/releases/tag/v1.0.0
