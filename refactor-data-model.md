# Data model refactor — flat Set + tags/modality + warmup/cooldown

## Goal

Replace the current `StrengthSet`/`ActivitySet` discriminated union with a single flat `Set`
model. Replace the fixed `exercise_type` enum with free-text `tags` and `modality` fields.
Add `warmup` and `cooldown` exercise groups to `TrainingSession`.

This unblocks the Groq parser (no `set_type` discriminator for the LLM to emit), makes the
model extensible to any sport or training style without code changes, and correctly models
mixed sets (e.g. timed strength work with both `weight_kg` and `duration_seconds`).

Design decisions are recorded in `docs/design.html`.

## Blast radius

| File | Change |
|---|---|
| `models/models.py` | Drop `StrengthSet`, `ActivitySet`, `AnySet`; create flat `Set`; update `Exercise` and `TrainingSession` |
| `models/__init__.py` | Update exports |
| `db/schema.sql` | Drop `set_type`, drop `exercise_type`, add `tags TEXT[]`, `modality TEXT`, `exercise_group TEXT DEFAULT 'main'` to exercises |
| `db/insert.py` | Update insert logic for new schema |
| `db/fetch.py` | Update fetch queries |
| `agent/llm_parser.py` | Update `TrainingLogLLMExtract`, `SYSTEM_PROMPT`, Groq prompt |
| `agent/validation_card_builder.py` | Update for flat `Set` (remove `StrengthSet`/`ActivitySet` branches) |
| `api/schemas.py` | Drop `set_type` from `WorkingSetOut`; add `tags`, `modality` to `ExerciseOut` |
| `cli/validate.py` | Update `_print_session_summary` (no `exercise_type`) |
| `parser/extract.py` | Remove `exercise_type` routing |
| `parser/parse.py` | Remove `set_type` and `exercise_type` from output dicts |
| `tests/test_models.py` | Full rewrite of StrengthSet/ActivitySet/AnySet tests → flat Set tests |
| `tests/test_db.py` | Update all fixtures and assertions |
| `tests/test_queries.py` | Remove `set_type` from expected dicts |
| `tests/test_processor.py` | Update DB column assertions |
| `tests/test_api.py` | Remove `set_type` from expected response |
| `tests/test_agent_*.py` | Remove `exercise_type`/`set_type` from all fixtures |
| `tests/test_parse.py` | Remove `set_type` assertions |

## Steps

- [x] **Step 1 — Pydantic models + LLM extract model** · branch: `refactor/data-model-pydantic-models`
  - WorkingSet: flat model replacing StrengthSet/ActivitySet; all measurement fields optional
  - Exercise: drop exercise_type; add tags (NASM/NSCA), modality, movement_pattern (List[str])
  - SessionWarmup, SessionCooldown: new models (number, name, reps, duration_seconds, notes)
  - TrainingSession: add warmup/cooldown; sequential numbering validated per-group
  - TrainingLogLLMExtract: add warmup/cooldown; SYSTEM_PROMPT updated
  - Downstream steps (insert.py, validation_card_builder.py, etc.) import-stub only
  - Affected tests marked skip with unblock reason; test_models.py rewritten parametrized
  - Gate 1: 114 passing. Gate 2 (Groq E2E) deferred — run after Step 2 when full pipeline works
  - Squash-merged to refactor/data-model · 2026-05-13

- [x] **Step 2 — DB schema, insert, fetch, API** · branch: `refactor/data-model-db-and-api`
  - `db/schema.sql`: drop `set_type` column from `working_sets`; drop `exercise_type` column
    from `exercises`; add `tags TEXT[]`, `modality TEXT`, `exercise_group TEXT NOT NULL DEFAULT 'main'`
    to `exercises`
  - `db/insert.py`: update exercise insert (tags, modality, exercise_group); update working_set
    insert (no set_type, no isinstance branching); insert warmup/cooldown exercises with
    `exercise_group = 'warmup'` / `'cooldown'`
  - `db/fetch.py`: update SELECT queries (no set_type, add tags/modality/exercise_group)
  - `api/schemas.py`: drop `set_type` from `WorkingSetOut`; add `tags`, `modality`,
    `exercise_group` to `ExerciseOut`
  - Update `tests/test_db.py`, `tests/test_queries.py`, `tests/test_processor.py`, `tests/test_api.py`
  - Gate: `pytest tests/` green with Docker running (integration tests need DB)

- [x] **Pre-Step 3 — Schema column audit** · Done 2026-05-13

  DB audit ran against live test DB. Findings:

  **Fixed:** `exercise_group TEXT` was still in the live test DB but absent from `schema.sql`.
  Dropped via `ALTER TABLE exercises DROP COLUMN exercise_group` (no code references remained).

  **Clean — no action needed:**
  - `sessions`: all 14 data columns map 1:1 to `TrainingSession` fields. `created_at` is a DB-side
    default (correct). `source_file` exposed (see below).
  - `exercises`: all remaining columns (`tags`, `modality`, `movement_pattern`, goal_*, `form_cues`,
    `target_muscle_groups`, `rep_tempo`, `warmup_notes`, `notes`) map correctly.
  - `working_sets`: bilateral rep columns (`reps_full`, `reps_partial`) and unilateral columns
    (`left/right_reps_full/partial`) are intentionally mutually exclusive. `rest_minutes` /
    `rest_seconds` correctly map from `Rest` model (validator enforces only one is set).
  - `warmup_sets`: all 5 columns map to `WarmupSet` fields.

  **Resolved:** `sessions.source_file` — decided to expose. Added to `get_session` SELECT in
  `fetch.py` and added `source_file: Optional[str]` to `SessionDetail` in `api/schemas.py`.
  Committed to `refactor/data-model` (commit `6f17e3a`). Suite: 282 passed, 55 skipped, 0 failed.

  **Schema rename (2026-05-13):** `session_movements` (single table with `movement_group` discriminator)
  split into two explicit tables: `warmups` and `cooldowns`. `movement_group` column dropped.
  `SessionMovementOut` → `MovementOut` in `api/schemas.py`. Updated: `schema.sql`, `insert.py`,
  `fetch.py`, `api/schemas.py`, `test_db.py`. Suite: 282 passed, 55 skipped, 0 failed.

- [x] **Step 3 — Card builder, rules parser, CLI** · branch: `refactor/data-model-parser-and-card`
  - `agent/validation_card_builder.py`: remove `isinstance(s, StrengthSet)` / `_activity_row`
    branching; one unified row builder for flat `Set`
  - `cli/validate.py`: update `_print_session_summary` (no `exercise_type`)
  - `parser/extract.py`: remove `exercise_type: activity` detection and routing
  - `parser/parse.py`: remove `set_type` from all output dicts; remove `exercise_type` routing;
    produce flat set dicts
  - Update `tests/test_agent_validation_card_builder.py`, `tests/test_agent_llm_extract_validator.py`,
    `tests/test_agent_llm_orchestrator.py`, `tests/test_cli_ai_parser.py`, `tests/test_parse.py`
  - Gate: `pytest tests/` fully green

- [x] **Step 4 — E2E validation** · branch: `refactor/data-model-e2e`
  - `traininglogs validate` — all 3 fixture types (strength, activity, unilateral) → exit 0. Done.
  - `traininglogs log --test --no-commit --parser rules` — all 3 fixtures inserted cleanly into
    test DB. No local mirror write. Done.
  - Added `--test` flag to `cli/log.py`: routes to TEST_DATABASE_URL, skips LOCAL_DATABASE_URL.
  - API smoke test: deferred — Supabase not reachable locally; covered in Step 6 (cloud).
  - Suite: 337 passed, 0 skipped, 0 failed.

- [x] **Step 5 — Full data validation (local)** · branch: `chore/validate-v3-local` → merged to `dev` (commit `9b62a9f`)
  - `repopulate_db.py --regen` populated validation DB (v3 schema) from all 121 .md inputs, 0 failed.
    Fix: skip `program.md` in glob (metadata file, not a session — pre-existing gap from TL-2).
  - `validate_v3_local.py`: full value comparison validation DB vs local mirror.
    All 121 sessions, 1009 exercises, 2469 working_sets, 647 warmup_sets match exactly.
    `warmups`/`cooldowns` empty. Schema diffs confirmed: `set_type` (2469 non-null in v2, absent v3),
    `exercise_type` (1009 non-null in v2, absent v3), `tags`/`modality`/`movement_pattern` all NULL in v3.
  - **AI parser spot-check (2026-05-13):** live interactive test with `--parser groq` on `tests/fixtures/test_session_asif.md`.
    Confirmation card showed: Phase 1, Week 1, 101 min, 13 warmup movements, 6 exercises, 6 cooldown movements. Groq tool-calling fixed (was sending JSON mode). SYSTEM_PROMPT improved: explicit extraction rules for focus, session_duration_minutes, phase/week, is_deload_week, warmup_sets rep_count as int, modality as single string.
  - Card architecture updated: `SessionMovementSection` + `MovementRow` added to `validation_card_data.py`; `TerminalRenderer` renders warmup/cooldown sections. Phase/week shown unconditionally (not nested under program).
  - Design issues deferred (to design session before Step 6): (a) session-level `notes`/remarks field in `TrainingLogLLMExtract`; (b) RPE in remarks blocks vs inline; (c) unknown user fields that don't map to schema (e.g. "Movement:" keyword collision).
  - Suite: 337 passed, 0 skipped, 0 failed.

- [x] **Design session (resolved 2026-07-26)** · branch: `chore/session-notes-and-remarks`, grounded in the real
  `inputs/sessions/test_session_asif.txt` spot-check file (still misplaced — see follow-ups).
  - **(a) Session-level notes**: added `notes: Optional[str]` to `TrainingSession` and
    `TrainingLogLLMExtract` (+ `sessions.notes` TEXT column). Every level already had its own
    `notes` except the session; the design question was really attachment priority, not a new
    field. Rule: attach unmapped text to the MOST SPECIFIC level it's clearly tied to (a named
    set → that set's notes; a named exercise/movement → that item's notes); session-level
    `notes` is the fallback only when nothing more specific applies. Confirmed live via
    `--parser groq` on `tests/fixtures/valid/adhoc_remarks_and_session_notes.md`.
  - **(b) RPE stated once per exercise (remarks block, not inline)**: defaults to the LAST set
    of that exercise (upper bound if a range), flagged `uncertain_fields`; an explicitly named
    set ("top set RPE 9") overrides the default. Never spread across all sets — this was the
    exact shape of the earlier-observed Groq over-propagation bug. Confirmed live: 4 identical
    Bench Press sets with one trailing "RPE: 7-8" remark → RPE landed only on set 4. Known gap:
    Groq applied the value correctly but did not reliably add it to `uncertain_fields` — the
    value is still visible and correctable in the confirmation card, just without the `?`
    emphasis. Documented as a watch-item, not blocking (same category as the earlier RPE
    over-propagation quirk).
  - **(c) "Movement:" / unknown keywords**: dropped as a focus alias entirely (checked all real
    historical inputs — it appears exactly once, and is fully redundant with the session's own
    first exercise name). Decided NOT to maintain a growing alias dictionary in `SYSTEM_PROMPT`
    — that reintroduces brittle keyword-matching into what's supposed to be semantic
    understanding, and doesn't scale to other users' vocabulary. General rule instead: any
    labeled field that isn't `focus`/`program`/etc. just has its content routed into the nearest
    applicable notes field per rule (a) — no new field, no alias list, ever-growing per user.
  - Suite: 370 passed, 0 skipped, 0 failed (was 355; +15 new tests across models, llm_parser,
    validation_card_builder, renderer, db).

- [ ] **Step 6 — Full data validation (cloud)** · strategy TBD when we get here
  - Same sequence as Step 5 (rules parser first, then AI parser spot check)
  - Separate DB vs separate tables in Supabase: decide at the time
  - Once validated: purge old data; keep new

- [ ] **Step 7 — JSON comparison**
  - Keep a copy of current `output_training_logs_json/` before any regen
  - Compare regenerated JSON files against the copy after cloud is validated
  - This is last — JSON tends to get overwritten

## ▶ Resume here

**Design session complete (2026-07-26), all 3 open questions resolved and implemented on
`chore/session-notes-and-remarks`. Next: merge to `dev`, then cut `chore/validate-v3-cloud`
for Step 6.**

`dev` state before this branch: 355 passed. On this branch: 370 passed, 0 skipped, 0 failed.

Known follow-ups (non-blocking):
- `inputs/sessions/test_session_asif.txt` is a real programmed session (Phase One, Week 1)
  sitting in the ad-hoc `inputs/sessions/` directory — per the movement-skill reorg, it
  belongs at `inputs/programs/<slug>/phase_1/week_1/` instead. Never logged to the DB. Apoorva
  to decide: move + log for real, or leave as a spot-check artifact.
- Groq applies remark-block RPE to the correct (last) set but doesn't reliably flag it in
  `uncertain_fields`. Value is still visible/correctable in the card. Watch, don't chase —
  same category as the earlier RPE over-propagation quirk.

**Then cut `chore/validate-v3-cloud` from `dev` and design Step 6 strategy:**
- Separate Supabase DB vs separate tables in existing Supabase project?
- Likely: separate schema or temp tables to avoid touching live data.
