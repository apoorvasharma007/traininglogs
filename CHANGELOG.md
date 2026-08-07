# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — capture and interpretation layers (Phase 2, step 1)

- `raw_inputs` table: what the person actually produced, never edited. `id`, `content`,
  `source_kind` (`markdown`|`photo`|`speech`, CHECK-constrained), `source_file` (null for
  spoken or pasted input), `checksum` (sha256 of the content), `captured_at`. Identical text
  is deliberately **not** deduplicated — repeating a session is a real thing a person does, and
  collapsing two captures into one would make them indistinguishable. The checksum is indexed
  so finding duplicates is a query; deciding what to do about them belongs to the ingest path.
- `extractions` table: one attempt at reading a raw input. `raw_input_id` FK (cascading),
  `model`, `prompt_version`, `extract` (JSONB), `uncertain_fields`, `warnings`, `status`
  (`pending`|`confirmed`|`rejected`, CHECK-constrained), `created_at`, `confirmed_at`.
  Many-to-one by design: re-reading the same text with a better model or a fixed prompt must not
  require the person to write anything twice.
- `insert_raw_input`, `insert_extraction`, `content_checksum` in `db/insert.py`; `get_raw_input`,
  `find_raw_inputs_by_checksum`, `get_extraction`, `get_extractions_for_raw_input` in
  `db/fetch.py`.
- `prompts.PROMPT_VERSION` — a 12-character hash of the three live prompts, recomputed on
  import. Derived rather than declared, because a hand-maintained version constant is only
  correct while someone remembers to bump it.

Nothing writes to these tables yet — this step is purely additive, so no existing behaviour
changes. `schema.sql` uses `CREATE TABLE IF NOT EXISTS` throughout, so applying it to an
existing database adds the two tables and touches nothing else.

Validation rules in effect: `raw_inputs.source_kind` must be one of `markdown`/`photo`/`speech`;
`extractions.status` must be one of `pending`/`confirmed`/`rejected`; an extraction cannot
reference a raw input that does not exist, and is deleted with it.

### Fixed — extraction reliability (2026-08-06)

A measurement run scored 215/277 on core fields, down from 98.8%. The cause was not extraction
quality: on every exercise the model actually returned it was **147/147**. Five worker calls
returned `{"number": 1}` — no name, no sets — and each became an exercise-shaped hole.

- **Validation now runs inside the provider's retry loop.** `ExtractionProvider.extract()` takes
  a `validate` callback and re-asks when the payload fails it. Previously validation lived in the
  callers (`parse`, `segment`, `extract_shell`, `extract_exercise`), one layer above the loop, so
  a tool call that parsed as JSON but didn't satisfy its model got none of its three attempts.
  The reask replays the failed `tool_use` and answers it with a `tool_result` carrying
  `is_error`, so the model sees what it sent and why it was wrong. Groq uses the equivalent
  OpenAI `tool` role shape.
- **`strict: true` on Anthropic tool definitions.** Grammar-constrained sampling makes a call
  that omits a required field impossible to generate, rather than something to recover from.
  `strict_schema()` adds the required `additionalProperties: false`; a test pins that the live
  schemas stay inside the supported subset, since the API answers an unsupported schema with a
  400 rather than degrading quietly.
- **An extract with no working sets and no warmup sets is rejected.** It was schema-valid and
  invisible: `check_sources_are_real()` and `check_sets_are_numbered_and_sourced()` both iterate
  over the sets that came back, so zero sets produced zero findings. One token's difference from
  the observed failure would have written a clean-looking session with every set silently
  missing. It now takes the retry path, and only becomes a flagged placeholder if every attempt
  comes back empty.
- **Removed `ExerciseExtract.number`.** The splitter already knows each exercise's position and
  `assemble()` overwrote whatever the worker reported, so the field asked the model for
  information that was discarded — and it was the one field the failing calls did fill.
  `to_exercise(number)` now takes the position from the caller.
- **A worker handed an isolated chunk is no longer told to find "exercise number N".** That
  instruction only makes sense in the full-document fallback, where it is still used.
- **Removed the exercise-count check in `audit()`.** `assemble()` appends exactly one exercise
  per split entry, extracted or placeholder, so the counts were equal by construction and the
  check could never fire — the same defect as the kg-token check removed before it.

Validation rules in effect: `ExerciseExtract` requires a non-empty `name` and at least one
working or warmup set; `SetExtract` requires `source_line` and a positive `number`.

### Added (v3.0.0 data model — Steps 1–5 complete, Step 6 (cloud validation) + Step 7 (JSON comparison) remaining)

- `WorkingSet`: flat model replacing `StrengthSet`/`ActivitySet`/`AnySet` discriminated union.
  All measurement fields optional (`weight_kg`, `rep_count`, `unilateral_rep_count`,
  `duration_seconds`, `distance_meters`, `heart_rate_bpm`). Mixed sets (e.g. timed strength work
  with both `weight_kg` and `duration_seconds`) are valid.
- `SessionWarmup`, `SessionCooldown`: new lightweight models (`number`, `name`, `reps`,
  `duration_seconds`, `notes`) for warmup and cooldown phases. Stored in their own
  `warmups`/`cooldowns` tables (not mixed into `exercises`).
- `TrainingSession.warmup`, `TrainingSession.cooldown`: `Optional[List[SessionWarmup/Cooldown]]`.
  Sequential numbering validated per-group independently (warmup, exercises, cooldown each start at 1).
- `Exercise.tags: Optional[List[str]]` — NASM OPT / NSCA-based vocabulary:
  `absolute_strength`, `muscle_growth`, `muscle_endurance`, `explosive_power`,
  `core_stabilization`, `balance_control`, `passive_flexibility`, `active_mobility`,
  `cardiorespiratory`, `saq`, `sport_specific`.
- `Exercise.modality: Optional[str]` — free-text equipment/modality descriptor
  (e.g. `"barbell"`, `"bodyweight"`, `"cable"`).
- `Exercise.movement_pattern: Optional[List[str]]` — list to support compound patterns;
  vocabulary: `squat`, `hip_hinge`, `push`, `pull`, `lunge`, `carry`, `rotation`.
- `TrainingLogLLMExtract`: `warmup` and `cooldown` fields added; `SYSTEM_PROMPT` updated with
  NASM/NSCA tag rules and warmup/cooldown extraction guidance.
- `GroqProvider`: free Groq API alternative to Anthropic for local testing; uses JSON mode.
  Selectable via `--parser groq`.
- Movement-skill intake: `SYSTEM_PROMPT` conventions for calisthenics, gymnastics rings,
  juggling, reaction drills, shadow boxing, and kettlebell/dumbbell work — usable both
  ad-hoc (unprogrammed) and mixed into a real structured phase/week program. No model
  changes — existing fields cover every case: skill-run counts (e.g. juggling catches)
  and skill-attempt counts (e.g. muscle-up tries) map to `rep_count` (attempts that
  complete cleanly are `full`, attempts that don't are `partial` — the same distinction
  a normal working set already makes; ordinary reps with varying form quality stay
  `full` regardless — only genuine attempt/clean phrasing triggers the split); static
  holds and timed rounds map to `duration_seconds`; reaction-time drills use `rep_count`
  for attempt counts with measured times (ms) in `notes`, never in a numeric field.
  Ad-hoc sessions (no program, no phase/week) leave `program`/`phase`/`week` all unset —
  no pseudo-program name is invented. `inputs/sessions/` is the documented location for
  these (mirrors the pre-existing "standalone session" concept already covered by
  `tests/test_processor.py`); `inputs/programs/` stays reserved for real structured
  programs. A session with phase/week but no stated program name also leaves `program`
  unset rather than guessing, since it belongs to a real program whose name lives
  outside the file text (usually the directory path). Copy-pasteable templates in
  `templates/`: `adhoc-template.md` + two worked examples (`adhoc-example-home-skills.md`,
  `adhoc-example-gym-calisthenics.md`) for `inputs/sessions/`, and
  `programmed-example-calisthenics-mixed.md` showing calisthenics mixed into a real
  phase/week session using the existing gym-log format (no new template needed there).
  Exercise prompt fix bundled in: `exercises` now explicitly excludes warmup/cooldown
  movements (previously ambiguous, occasionally double-counted).
- Session-level `notes: Optional[str]` on `TrainingSession` and `TrainingLogLLMExtract`
  (+ `sessions.notes` column), for remarks that don't belong to any specific exercise or
  set (e.g. an observation made before the first exercise). `SYSTEM_PROMPT` updated with a
  general catch-all: any text that can't be mapped to a structured field is attached as a
  note at the most specific level it clearly belongs to (a named set, a named exercise or
  movement, falling back to the session-level `notes` only when nothing more specific
  applies) — never silently dropped. RPE stated once for a whole exercise (a remarks block
  after all its sets, rather than inline per set) now defaults to the *last* set only (upper
  bound if a range), flagged `uncertain_fields`, with an explicitly named set overriding the
  default — replaces the previous undefined behavior that could spread one RPE value across
  every set in the exercise. Deliberately dropped `"Movement:"` as a `focus` alias rather
  than maintaining a growing keyword-alias list — it appeared exactly once across all real
  historical inputs and is redundant with the session's own exercise list; unmapped labels
  now just fall through to the notes rule above instead of needing bespoke handling.
  `ValidationCardBuilder`/`TerminalRenderer` updated: a session-level note preview renders
  right after the session header, same truncation behavior as exercise notes.

### Fixed

- `AnthropicProvider`/`GroqProvider` now pin `temperature=0` on every extraction call.
  Neither pinned a temperature before, so identical input to `--parser groq` could produce
  materially different extractions between calls — in one investigated case, two of three
  repeated live calls on the same real session file silently dropped an exercise-level RPE
  remark entirely (no value, no note) for the last 3 of 6 exercises, while the third call
  extracted every one correctly. Ruled out token-limit truncation first (`finish_reason:
  tool_calls`, not `length`) before concluding it was sampling-temperature variance on what
  should be a deterministic extraction task.

### Removed (v3.0.0 data model)

- `StrengthSet`, `ActivitySet`, `AnySet` — replaced by flat `WorkingSet`.
- `Exercise.exercise_type` — replaced by `tags` + `modality`.
- `set_type` discriminator field — no longer emitted by the LLM or stored anywhere.

### Removed

- `traininglogs log --publish` and `cli/log.py::_publish_dashboard()` — dead code.
  It pushed a copy of the dashboard to `website/static/training-almanac/index.html`,
  a path that predates the Wave 7 website restructure and that nothing writes to
  anymore. The website now pulls `docs/index.html` directly from this repo at
  deploy time instead, so publishing a copy is unnecessary. `--publish` was a
  silent no-op before this removal. Docs (`README.md`, `CLAUDE.md`,
  `.claude/testing-guide.md`, `docs/design.html`) updated to match.

---

### Added

- `--parser ai|rules` flag on `traininglogs validate` and `traininglogs log`.
  `--parser ai` (default) runs the `LLMOrchestrator` confirmation loop before
  writing to the DB. `--parser rules` runs the existing deterministic pipeline.
- `processor.build_session_from_extract()` — converts a confirmed
  `TrainingLogLLMExtract` into a `TrainingSession`, injecting system fields
  (`session_id`, `user_id`, `user_name`, `data_model_version`,
  `data_model_type`) and path-derived program context.

- `agent/validation_card_builder.py`: `ValidationCardBuilder` — converts a
  `TrainingLogLLMExtract` into a `UserValidationCard` dataclass tree. Resolves
  `uncertain_fields` dot-paths (e.g. `"exercises.0.sets.1.rpe"`) to per-component
  `frozenset[str]` fields on `SessionHeader`, `ExerciseHeader`, `WarmupRow`, and
  `WorkingSetRow`. Formats rep strings (`"8"`, `"8+2"`, `"10L / 9R"`), failure
  technique summaries, and goal summaries.
- `agent/llm_extract_validator.py`: `LLMExtractValidator` — applies a user's
  freeform correction to a `TrainingLogLLMExtract` via the `ExtractionProvider`
  interface, then re-validates with Pydantic. Raises `LLMParserError` on permanent
  failure.
- `agent/llm_orchestrator.py`: `LLMOrchestrator` — full AI-parser flow: parse text
  → build card → render → stdin correction loop → re-render → repeat until user
  confirms → return validated `TrainingLogLLMExtract`. Injectable `input_fn` and
  `renderer` for testing.

---


### Added (pipeline evaluation, 2026-08-02)

- `scripts/eval_ab.py` — model A/B harness with an on-disk response cache keyed by the full
  request hash, a `--max-cost` abort, `--dry-run`, and per-call spend logging to `calls.jsonl`.
  No paid call is ever made twice, across runs or after a crash.
- `scripts/eval_arms.py` — pipeline-architecture comparison (`split-pf` / `split-nopf` / `mono`)
  scored automatically against the historical JSON in `output_training_logs_json/`, matched to
  each input by the `session_id` path hash. Numeric spine only; classification fields are not
  scored because they postdate that data.
- `assemble()` gained `use_parse_first` and `TRAININGLOGS_DISABLE_PARSE_FIRST` — a measurement
  escape hatch that runs the pipeline with `parse_exercise_block()` disabled. Explicitly not a
  production mode; removed together with parse-first in roadmap Phase 1.
- `roadmap.md` — single forward plan superseding `orchestration-refactor-plan.md`,
  `extraction-accuracy-plan.md`, and the Cloud Deployment Wave in `pre-online-plan.md`.

### Fixed

- Non-retryable API errors (billing, quota, permission) now raise `LLMParserError` immediately
  instead of consuming the full reask budget. Previously a credit-balance 400 burned three
  attempts on a guaranteed failure and buried the real cause under "failed after 3 attempts".
  Applies to both `AnthropicProvider` and `GroqProvider`.

### Removed

- `scripts/spot_check_ai_parser.py` — imported `traininglogs.agent.llm_parser`, removed in the
  split-extraction refactor; the script had been dead since.
- `scripts/validate_with_model.py` — Groq-specific comparison runner, superseded by
  `scripts/eval_arms.py`.


### Removed (parse-first, 2026-08-03)

- `parse_exercise_block()` and `src/traininglogs/agent/exercise_block.py` — the deterministic
  per-exercise block parser. Measurement showed it fired on **0 of 10 exercises in real input
  files**: it required exact-match `Warmup:` / `Sets:` / `Remarks:` header lines, while real
  logs use markdown (`### Working Sets`). It had never run in production, only against the older
  `tests/fixtures/valid/programmed_*.md` format it was validated on. The pure-AI path scores
  ~99.7% on the numeric spine across 6 real sessions with Haiku 4.5.
- `extract_exercise_labels()`, `LABELS_SYSTEM_PROMPT`, `LABELS_TOOL_NAME`/`_DESCRIPTION`, and
  the `ExerciseLabelsExtract` schema — the narrow classification-only worker path, reachable
  only when parse-first succeeded.
- `assemble()`'s `use_parse_first` parameter and `TRAININGLOGS_DISABLE_PARSE_FIRST` env var —
  the measurement escape hatch added to run this comparison. `assemble(text, provider)` again.
- `tests/test_agent_exercise_block.py`, `tests/test_agent_exercise_labels.py`, and
  `TestAssembleReproducesOriginalFailures` in `tests/test_agent_assembler.py`. **Coverage note:**
  that last class proved two of the three original extraction failures were structurally
  impossible — a guarantee that held *because* the parser supplied the numeric spine. With the
  model supplying it instead, the same tests would only assert that a scripted value came back
  unchanged, so they were deleted rather than rewritten into something weaker than they look.
  That coverage moves from unit-level structural proof to measurement: `scripts/eval_arms.py`
  scores real extractions against historical data, and `audit()` (strengthened next in roadmap
  Phase 1) is the runtime guard.
- `eval_arms.py`'s `split-pf` arm, which is no longer distinguishable from `split`.

Suite: 467 passed, 0 failed, 0 skipped (was 483; the 16 removed covered deleted code).

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
- `tests/fixtures/valid/standalone_session.md` — canonical fixture for a
  session with no program context.
- `tests/test_validate.py` — 7 tests covering `traininglogs validate` against
  valid and invalid fixtures.
- `api/schemas.py`: `SessionSummary`, `SessionDetail`, `ExerciseOut`,
  `WorkingSetOut`, `WarmupSetOut`, `ExerciseHistoryRow`.
- Supabase cloud DB as primary database. `DATABASE_URL` targets Supabase; schema
  applied and all 121 historical sessions populated.
- Fly.io deployment for the FastAPI. `Dockerfile` and `fly.toml` added; API live
  at https://traininglogs-api.fly.dev.
- Optional local Postgres mirror: CLI writes to `LOCAL_DATABASE_URL` when set and
  reachable, skips silently if not.
- `scripts/apply_schema_supabase.py` — one-shot schema migration helper for Supabase.
- `.env.example` updated to document `DATABASE_URL` (Supabase) and
  `LOCAL_DATABASE_URL` (optional local mirror).
- `inputs/programs/bodybuilding_transformation_system/program.md` — program metadata
  file consumed by the dashboard for display.

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
- Dashboard visual/design refresh: six-section layout, cleaner white theme,
  Inter + JetBrains Mono typography, and program auto-discovery docs aligned with
  `scripts/build_dashboard.py` and `docs/index.html` generation flow.
- Dashboard (`scripts/build_dashboard.py`, `docs/index.html`): e1RM section dropped;
  programs now auto-discovered from `inputs/programs/`; overview layout streamlined.
- `docs/design.html`: updated to reflect Supabase primary DB, dual-write CLI behavior,
  Fly.io API deployment, and dashboard auto-discovery of programs.

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
- `validate.py`: imported deleted `_to_primitive` and `is_dataclass`; replaced
  old bridge loop with the current pipeline (mirrors `process_md_file` minus
  DB/JSON steps).
- `parse.py`: `program`, `phase`, `week`, `duration` are now Optional — absent
  program context fields return `None` (standalone sessions). Hardcoded program
  name and author defaults removed.
- `processor.py`: JSON output path crashed for standalone sessions (`TypeError`
  on `None` program/phase/week). Now routes to `output_dir/sessions/` when
  program context is absent.
- `parse.py`: silent `0 x 0` fallback in `_parse_working_set_line` removed;
  now raises `ValueError` like all other malformed-line paths.
- `parse.py`: program-context trigger changed from program-presence to
  phase/week-presence — real input files have no `- Program:` line; phase and
  week are the co-dependent signals that mark a session as program-affiliated.
  Either alone is malformed and raises `ValueError`.
- `processor.py`, `validate.py`: `_derive_program_context()` added — infers
  `program`, `phase`, and `week` from the `inputs/programs/<slug>/phase_N/week_N/`
  directory structure and injects them when file metadata omits them. Program
  name in file metadata still wins if present.
- `validate.py`, `log.py`: `Path.resolve()` applied to user-supplied paths so
  session IDs are correctly path-derived (SHA256 of full relative path) rather
  than filename-only.
- `parse.py`: working set lines with unit-annotated weights (`30 kg x 6`)
  now parse correctly; unit is stripped, value stored as kg.
- `parse.py`: rep count is now optional on working set lines — failure sets
  that log weight and RPE without a rep count are valid (`57 x RPE 10 failure:llp(8)`).
- Two corrupt input lines corrected (user-approved):
  `phase_2/week_11/lower_strength`: RPE 13 → RPE 10;
  `phase_2/week_6/push_hypertrophy`: `2. 13.6` → `2. 13.6 x 12`.
- `schema.sql`: `created_at TIMESTAMPTZ DEFAULT now()` added to sessions;
  `idx_exercises_session_id` and `idx_working_sets_exercise_id` indexes added.
- `api/app.py`: `CORSMiddleware` (driven by `ALLOWED_ORIGINS` env var);
  `SimpleConnectionPool` replaces per-request connections; `apply_schema`
  removed from lifespan; Pydantic response models on all routes.
- `scripts/repopulate_db.py`: `--regen` flag uses `REGEN_DATABASE_URL`
  (port 5434 staging DB) with safety guards against cross-target accidents.
- `scripts/validate_regen.py`: strict exact-count validation plus 10-file
  spot-check (live parse vs DB) before any prod repopulate.
- `docker-compose.yml`: `db_regen` service at port 5434.
- `.claude/db-migration.md`: full regen process documented with step-by-step
  commands and the explicit prod-approval rule.
- `api/app.py`: `API_KEY` was read at module import time — test env overrides applied
  after import had no effect. Now read at call time.
- CI workflow: `docs/**` path was missing from push/PR triggers — edits to
  `docs/design.html` did not trigger CI runs.

### Removed

- `models_dataclass.py` — legacy parallel dataclass layer.
- Old `--phase`/`--week` as standalone required args (replaced by the
  `--program/--phase/--week` combination or a positional target).
- `docs/architecture.md` — content subsumed by `docs/design.html`.
- `apply_schema` removed from `traininglogs log` — schema is never auto-applied at
  runtime; migrations are explicit. Dead `apply_schema` import removed from
  `processor.py` (was imported but never called).
- `load_dotenv()` removed from `processor.py` top level — library modules must not
  have side effects. Moved to the correct call site in `log.py`, now runs before
  the `DATABASE_URL` check (fixing a latent bug where `.env` variables were not
  loaded when that check ran).
- `repopulate_db.py --regen` safety guard changed from a negative check
  (`"5432" in url and "5434" not in url`) to a positive check — URL must contain
  `5434` or `traininglogs_regen`; this was blocking Supabase cloud URLs.
- Unused `exercise_e1rm_trend` tests removed from `test_queries.py` (query and
  dashboard section were both dropped).

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
