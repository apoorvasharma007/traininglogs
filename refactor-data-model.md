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

- [ ] **Step 1 — Pydantic models + LLM extract model** · branch: `refactor/data-model/pydantic-models`
  - Drop `StrengthSet`, `ActivitySet`, `AnySet` from `models/models.py`
  - Create flat `Set(BaseModel)`: inherits all fields from both (weight_kg, rep_count,
    unilateral_rep_count, rep_quality_assessment, failure_technique, duration_seconds,
    distance_meters, heart_rate_bpm); all optional; validators from both classes preserved
  - `Exercise`: drop `exercise_type`, add `tags: Optional[List[str]] = None`,
    `modality: Optional[str] = None`
  - `TrainingSession`: add `warmup: Optional[List[Exercise]] = None`,
    `cooldown: Optional[List[Exercise]] = None`
  - Update `models/__init__.py` exports
  - `agent/llm_parser.py`: update `TrainingLogLLMExtract` to match flat `Set` (no `set_type`,
    no `exercise_type`; add `tags`, `modality`); update `SYSTEM_PROMPT` (remove `set_type` rule,
    add tags/modality extraction rules, fix phase-as-integer rule); update `GroqProvider` JSON
    addendum to drop `set_type` requirement
  - Update `tests/test_models.py`: replace StrengthSet/ActivitySet/AnySet tests with flat Set
    tests; add tests for tags, modality, warmup, cooldown
  - Update `tests/test_agent_llm_parser.py` fixtures to remove `set_type`/`exercise_type`
  - Gate 1: `pytest tests/test_models.py tests/test_agent_llm_parser.py` green (no DB needed)
  - Gate 2: `traininglogs validate inputs/sessions/test_session_asif.txt --parser groq` passes
    and shows a correct confirmation card — this proves the parser improvement before any
    downstream changes are made

- [ ] **Step 2 — DB schema, insert, fetch, API** · branch: `refactor/data-model/db-and-api`
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

- [ ] **Step 3 — Card builder, rules parser, CLI** · branch: `refactor/data-model/parser-and-card`
  - `agent/validation_card_builder.py`: remove `isinstance(s, StrengthSet)` / `_activity_row`
    branching; one unified row builder for flat `Set`
  - `cli/validate.py`: update `_print_session_summary` (no `exercise_type`)
  - `parser/extract.py`: remove `exercise_type: activity` detection and routing
  - `parser/parse.py`: remove `set_type` from all output dicts; remove `exercise_type` routing;
    produce flat set dicts
  - Update `tests/test_agent_validation_card_builder.py`, `tests/test_agent_llm_extract_validator.py`,
    `tests/test_agent_llm_orchestrator.py`, `tests/test_cli_ai_parser.py`, `tests/test_parse.py`
  - Gate: `pytest tests/` fully green

- [ ] **Step 4 — E2E validation** · branch: `refactor/data-model/e2e`
  - Run `traininglogs validate tests/fixtures/strength_session.md --parser ai`
  - Run `traininglogs validate tests/fixtures/strength_session.md --parser groq`
  - Run `traininglogs validate tests/fixtures/strength_session.md --parser rules`
  - Run `traininglogs log tests/fixtures/strength_session.md --no-commit`
  - API smoke test: `GET /sessions`, `GET /sessions/{id}`, `GET /exercises/{name}/history`
  - All pass → merge base branch to `dev`

- [ ] **Step 5 — Historical data regen** · branch: `chore/historical-data-regen`
  - Separate branch, cut after base branch is on `dev` and suite is green
  - Follow `regen-historical.md` process exactly
  - Regen to fresh output dir; validate side-by-side; get explicit approval before swapping

## ▶ Resume here

**Not started.** Cut `refactor/data-model` base branch from `dev`, then start Step 1.

```bash
cd /Users/apoorvasharma/Projects/traininglogs
git checkout dev
git checkout -b refactor/data-model
git checkout -b refactor/data-model/pydantic-models
```

First file to touch: `src/traininglogs/models/models.py` — drop `StrengthSet`, `ActivitySet`,
`AnySet`; rename/reshape `WorkingSet` into the flat `Set`.
