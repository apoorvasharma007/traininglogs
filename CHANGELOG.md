# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
