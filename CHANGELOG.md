# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned — data model flexibility + activity support

Design decisions made 2026-05-06. Not yet implemented.

#### `TrainingSession`
- Make `program`, `program_author`, `program_length_weeks`, `phase`, `week`,
  `is_deload_week`, `focus`, `session_duration_minutes` all `Optional` — enables
  ad-hoc workouts that don't belong to a program.
- Add `weight_unit: Literal["kg", "lbs"] = "kg"` at session level. Lbs is
  converted to kg at parse/input time; only kg is stored. Future: duplicate
  column + dashboard toggle (deferred).

#### `WorkingSet` — inheritance refactor
- Refactor `WorkingSet` into a base class carrying only shared fields:
  `number`, `rpe`, `rest: Optional[Rest]`, `notes`.
- Add `Rest(BaseModel)` with `minutes: Optional[int]` and
  `seconds: Optional[int]`. Validators: `minutes` 0–15, `seconds` 0–900,
  and a model validator that rejects both being set simultaneously.
  `StrengthSet` populates `rest.minutes`; `ActivitySet` populates
  `rest.seconds`. Replaces bare `actual_rest_minutes` int field on the old
  `WorkingSet`.
- Add `StrengthSet(WorkingSet)` — carries `weight_kg` (Optional), `rep_count`
  (Optional), `unilateral_rep_count` (Optional), `rep_quality_assessment`
  (Optional), `failure_technique` (Optional). Owns the
  `failure_technique_requires_rpe_10` validator.
- Add `ActivitySet(WorkingSet)` — carries `duration_seconds` (Optional),
  `distance_meters` (Optional), `heart_rate_bpm` (Optional). Covers running,
  swimming, sprinting, striking, kicking, drills, and unweighted stretching.
- Add `AnySet` discriminated union (`StrengthSet | ActivitySet`) on `set_type`.
- Add `UnilateralReps(BaseModel)` with `left: Optional[RepCount]`,
  `right: Optional[RepCount]` for tracking left/right imbalance per set.

#### `Exercise`
- `working_sets: List[WorkingSet]` → `sets: Optional[List[AnySet]]`.
- Add `exercise_type: Literal["strength", "activity"] = "strength"`. Default
  exists for backwards compatibility with historical data only — the AI agent
  prompt must always set this explicitly and never rely on the default.
- `WarmupSet` stays as a separate field and class — warmup volume is not
  performance data and should not be mixed into working sets.

#### `Goal`
- `weight_kg`, `sets`, `rep_range` → `Optional` (were required, broke for
  non-strength exercises).
- `rest_minutes: Optional[int]` → `rest: Optional[Rest]` — consistent with
  set-level rest; goal can prescribe either minutes (strength) or seconds
  (cardio intervals).
- Add `distance_meters: Optional[float]`, `target_duration_seconds: Optional[int]`
  for cardio/interval goals (e.g. 8 × 40 m sprints in under 5 s each).

#### DB migration (additive, no destructive changes)
- `working_sets`: add `set_type TEXT NOT NULL DEFAULT 'strength'`,
  `duration_seconds INT`, `distance_meters NUMERIC`, `heart_rate_bpm INT`,
  `left_reps_full INT`, `left_reps_partial INT`, `right_reps_full INT`,
  `right_reps_partial INT`; add `rest_seconds INT` alongside existing
  `rest_minutes` (both kept — minutes for strength, seconds for activity).
- `sessions`: add `weight_unit TEXT NOT NULL DEFAULT 'kg'`.
- `exercises`: add `exercise_type TEXT NOT NULL DEFAULT 'strength'`.

#### Testing plan

**Phase 1 — model unit tests** (`tests/test_models_v2.py`)

Run after model changes, before touching any pipeline code. Existing tests must
still pass. New tests must cover:
- `Rest` — valid minutes, valid seconds, both set simultaneously (must fail),
  minutes > 15 (fail), seconds > 900 (fail)
- `UnilateralReps` — valid left/right, both None (valid)
- `StrengthSet` — all existing `WorkingSet` tests ported + `rest.minutes`,
  `unilateral_rep_count`, `weight_kg=None` (bodyweight), `rep_count=None` (feel)
- `ActivitySet` — `duration_seconds`, `distance_meters`, `heart_rate_bpm`,
  `rest.seconds`
- `AnySet` discriminator — correct dispatch on `set_type` field
- `Goal` — `Rest` field, all previously required fields now Optional
- `TrainingSession` — ad-hoc session (no program/phase/week/focus), `weight_unit`

**Phase 2 — end-to-end pipeline** (manual validation against test DB + JSON)

Create sample markdown inputs in `input_training_logs_md/` that cover:
1. Standard strength session — regression baseline, output must match pre-change
2. Ad-hoc session — no program, phase, week, or focus fields
3. Lbs input — weight specified in lbs in markdown, stored as kg in DB and JSON
4. Activity exercise — a run or sprint block using `ActivitySet` fields
5. Unilateral set — left/right rep counts captured separately

Run `traininglogs log` against the test DB. Inspect JSON output in
`output_training_logs_json/` manually. Dashboard and API are out of scope for
this wave.

Note: the parser (`parser/extract.py`, `parser/parse.py`) is rule-based and will
need a markdown syntax decision for new fields (activity sets, unilateral reps,
lbs). This is a design step at the start of Phase 2 — do not skip it.

#### Deferred (not in this wave)
- Lbs duplicate column in DB + dashboard unit toggle.
- Superset / circuit support (sets linked across exercises).
- Sport/martial-arts session type (BJJ, Muay Thai).

## [1.0.0] - 2026-05-05

Initial tagged release. Seed entry — describes the system as it stands at v1.0.0
rather than reconstructing pre-1.0 history.

### Added

- **Pydantic v2 data model** (`models/models_v2.py`) as the canonical schema.
  Root type `TrainingSession` with nested `Exercise`, `WorkingSet`, `WarmupSet`,
  `Goal`, `RepRange`, `RepCount`, and a `FailureTechnique` discriminated union
  covering myo-reps, lengthened-partials, static holds, and drop sets.
- **Markdown parser** (`parser/extract.py`, `parser/parse.py`) — rule-based,
  deterministic, no LLM in the hot path. Bridges to Pydantic via the processor.
- **Processor CLI** (`processor/processor_v2.py`) — DB-first, JSON-second.
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
- **CI** — GitHub Actions runs the test suite on push and PR, and on tag-worthy
  pushes to `main` cuts a release and syncs the app version stamped in
  `docs/design.html`.
- **Technical design doc** at `docs/design.html` — single-page hand-written
  HTML, source of truth for the system's shape.

### Validation rules in effect

- `failure_technique` is only valid on working sets where `rpe == 10`.
- Exercise `number` fields must be sequential starting at 1.
- `week` must be between 1 and `program_length_weeks`.
- RPE must be a whole or half step between 1 and 10.
- `rest_minutes` and `actual_rest_minutes` must be between 0 and 15.
- Required string fields reject empty or whitespace-only values.

### Notes

- 121 historical sessions imported into the DB via
  `scripts/import_json_to_db_v2.py` (idempotent, supports `--overwrite`).
- Old dataclass-era modules (`models.py`, `insert.py`, `processor.py`) live
  in `archived/` and are not imported anywhere on the live path. They will be
  deleted when the AI agent (Track B) is wired in and the parser bridge is
  retired.

[Unreleased]: https://github.com/apoorvasharma007/traininglogs/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/apoorvasharma007/traininglogs/releases/tag/v1.0.0
