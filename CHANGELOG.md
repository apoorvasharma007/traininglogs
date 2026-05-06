# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Data model flexibility + activity support — in progress (as of 2026-05-06)

#### Done (squash-merged to `dev`)

- **Model refactor** (`models/models_v2.py`) — `WorkingSet` refactored into
  `StrengthSet` and `ActivitySet` subclasses with a `Rest` model; `AnySet`
  discriminated union on `set_type`; `UnilateralReps` added to `StrengthSet`;
  `Goal` fields made Optional with `distance_meters` and `target_duration_seconds`
  added; all program/phase/week/focus fields made Optional on `TrainingSession`;
  `weight_unit: Literal["kg", "lbs"] = "kg"` added to `TrainingSession`.
  See design decisions below for full field-level detail.
- **DB migration** (additive, no destructive changes) — `working_sets` gains
  `set_type`, `duration_seconds`, `distance_meters`, `heart_rate_bpm`,
  unilateral rep columns, and `rest_seconds`; `sessions` gains `weight_unit`;
  `exercises` gains `exercise_type`.
- **insert_v2.py** — updated to write all new columns.
- **Processor lbs conversion** (`processor_v2.py`) — detects `- Unit: lbs` in
  markdown metadata, recursively converts every `weight_kg` field in the
  primitive dict via `_convert_lbs_to_kg()`, sets `weight_unit = "lbs"` on the
  session before DB insert. Parser goal regex extended to accept `lbs`/`lb`.
- **Test suite** — 112 passing, 17 skipped (skips require `chore/historical-data-regen`).

#### Next — parser activity + unilateral support (`feature/parser-activity-unilateral`)

Markdown syntax decisions (made 2026-05-06):

- `### Working Sets` header → exercise is `strength` (existing, unchanged)
- `### Activity Sets` header → exercise is `activity` (new); no `**Type:**` field needed
- Activity set line format: `1. 20 min 2.5 km HR 145`
  - `<N> min` or `<N> sec` → `duration_seconds`
  - `<N.N> km` or `<N> m` → `distance_meters`
  - `HR <N>` → `heart_rate_bpm`
  - All tokens optional; any combination is valid
- Unilateral strength set format: `1. 30 x 8L/7R RPE 8 good`
  - `8L/7R` → `unilateral_rep_count: {left: {full: 8}, right: {full: 7}}`
  - Partial reps: `8L+1/7R+1` → `{left: {full: 8, partial: 1}, right: {full: 7, partial: 1}}`
  - Bilateral sets continue to use existing format (no change)
- Goal line stays bilateral-only for now (`**Goal:** 80 kg x 3 sets x 8-10 reps`)

Files to change:
1. `parser/extract.py` — recognize `### Activity Sets`, collect into `activity_sets`
   list, set `exercise_type = "activity"` on the exercise dict.
2. `parser/parse.py` — new `_parse_activity_set_line()` for `ActivitySet` objects;
   update `_parse_working_set_line()` to handle unilateral `8L/7R` format;
   update `_parse_exercise()` to build the correct set type.
3. `processor/processor_v2.py` — bridge step after `_to_primitive()` to rename
   `working_sets` → `sets` in each exercise dict (fixes the existing gap where
   `Exercise.sets` is always `None` in the validated model).
4. `tests/test_processor_v2.py` — add integration tests for an activity exercise
   session and a unilateral strength set.

#### Still deferred (not in this wave)
- Lbs duplicate column in DB + dashboard unit toggle.
- `fetch.py` updates for new columns (`set_type`, `exercise_type`, `weight_unit`,
  etc.) — 3 API tests remain skipped until this lands.
- `chore/historical-data-regen` — regenerate all historical JSON under new schema;
  unblocks 14 skipped import/query tests.
- Superset / circuit support (sets linked across exercises).
- Sport/martial-arts session type (BJJ, Muay Thai).

---

### Design decisions (reference)

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
- Add `StrengthSet(WorkingSet)` — carries `weight_kg`, `rep_count`,
  `unilateral_rep_count`, `rep_quality_assessment`, `failure_technique`.
- Add `ActivitySet(WorkingSet)` — carries `duration_seconds`, `distance_meters`,
  `heart_rate_bpm`. Covers running, cardio, drills.
- Add `AnySet` discriminated union (`StrengthSet | ActivitySet`) on `set_type`.
- Add `UnilateralReps(BaseModel)` with `left: Optional[RepCount]`,
  `right: Optional[RepCount]`.

#### `Exercise`
- `working_sets: List[WorkingSet]` → `sets: Optional[List[AnySet]]`.
- Add `exercise_type: Literal["strength", "activity"] = "strength"`.
- `WarmupSet` stays as a separate field.

#### `Goal`
- `weight_kg`, `sets`, `rep_range` → `Optional`.
- `rest_minutes: Optional[int]` → `rest: Optional[Rest]`.
- Add `distance_meters: Optional[float]`, `target_duration_seconds: Optional[int]`.

#### DB migration (additive, no destructive changes)
- `working_sets`: add `set_type TEXT NOT NULL DEFAULT 'strength'`,
  `duration_seconds INT`, `distance_meters NUMERIC`, `heart_rate_bpm INT`,
  `left_reps_full INT`, `left_reps_partial INT`, `right_reps_full INT`,
  `right_reps_partial INT`; add `rest_seconds INT` alongside existing
  `rest_minutes`.
- `sessions`: add `weight_unit TEXT NOT NULL DEFAULT 'kg'`.
- `exercises`: add `exercise_type TEXT NOT NULL DEFAULT 'strength'`.

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
