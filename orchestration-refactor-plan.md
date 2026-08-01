# Orchestration refactor: split the AI extraction into per-exercise calls

## Goal

Today the `--parser ai` path pulls the **whole** workout out in one big LLM call. On longer
sessions that call quietly drops details (an RPE, a remark) on the last few exercises. This
refactor replaces the single big call with several small ones — a splitter that lists the
exercises, one focused call per exercise, and one call for the session-level stuff — then
glues the results together with plain code and checks for anything dropped. Each small call
only has to handle one exercise, so it doesn't get overwhelmed. This only touches the AI
parser path; the deterministic `--parser rules` path is untouched.

## Locked design decisions

1. **Units of work:** one call for the *session shell* (date, program, phase, week, focus,
   duration, notes, warmup, cooldown) + one call per *exercise*. A separate *splitter* call
   lists how many exercises there are and their names, in order.
2. **Worker targeting:** the splitter returns an **ordered list with position numbers**
   (1st, 2nd, 3rd…). Each worker is told "extract the Nth exercise" and is given the whole
   note as context. Position, not name — so repeated names don't confuse it.
3. **Supersets = two separate exercises.**
4. **Drop-check (plain code, no LLM):** after assembly, verify the number of extracted
   exercises matches the splitter's count, and scan the raw text for RPE-shaped and
   weight-shaped numbers that didn't land in any field. Anything off gets flagged on the
   confirmation card.
5. **Failed worker = a flagged placeholder row on the card**, never a crash or a silent gap.
6. **Sequential calls** to start (speed is a non-issue at one user).
7. **Workers are self-contained:** `text (+ position) -> one Exercise`, no dependence on the
   other workers' results. This is the rule that makes a future mobile "process each exercise
   as you finish it" flow free instead of a rewrite. Hold firm on it.

## Blast radius

| File | Change |
|---|---|
| `src/traininglogs/agent/llm_parser.py` → split into `schemas.py` / `prompts.py` / `providers.py` / `extraction.py` | Step 1 breaks today's 284-line file into four cohesive modules (pure move, no behavior change) so the new pieces have an obvious home. `extraction.py` then holds the splitter/shell/worker functions, the assembler, and the drop-check. |
| `src/traininglogs/agent/llm_orchestrator.py` | Update imports after the file split; switch the AI path to call the new assembler instead of the monolithic `parse()`. |
| `src/traininglogs/agent/validation_card_builder.py` + `renderer.py` | Surface drop-check warnings and failed-exercise placeholders on the card. |
| `src/traininglogs/processor/processor.py` | `build_session_from_extract()` may need to tolerate placeholder/flagged exercises. Verify only. |
| Tests: `test_agent_llm_parser.py`, `test_agent_llm_orchestrator.py`, `test_agent_validation_card_builder.py`, `test_cli_ai_parser.py`, `test_movement_skill_conventions.py` | Update for the new call shape; add split-path tests. |
| `CHANGELOG.md`, `docs/design.html` | System shape changed → docs hygiene. |

## Branching

Base branch `refactor/split-extraction` cut from `dev`. One sub-branch per step below,
squash-merged back to the base once its suite is green. Base merges to `dev` only when every
step is done and the full suite is green.

## Code-quality bar (applies to every step, not a separate step)

Structure is decided in the plan (Step 1); craft is enforced continuously. Each sub-branch
must clear the same bar before it squash-merges: cohesive small functions, no duplicated
logic, type hints, the feature-checklist tests green (0 skipped, 0 failed). We do **not** add
a separate "clean up the agent layer" pass — we refactor only what the split forces, plus the
one file-split in Step 1. No speculative abstraction.

## Steps

- [x] **0. Base branch + this plan.** Cut `refactor/split-extraction` from `dev`, commit this file.
      Done 2026-08-01, commit `3ce133c`.
- [x] **1. Split the file into cohesive modules** (pure move, no behavior change). Broke
      `llm_parser.py` into `schemas.py` (`TrainingLogLLMExtract`, `LLMParserError`),
      `prompts.py` (`SYSTEM_PROMPT`), `providers.py` (`ExtractionProvider` +
      `AnthropicProvider`/`GroqProvider`), and `extraction.py` (`parse()`). Updated imports in
      `llm_orchestrator.py`, `llm_extract_validator.py`, `validation_card_builder.py`,
      `cli/validate.py`, and six test files (including the two `unittest.mock.patch()` targets
      in `test_agent_llm_parser.py`, which had to follow `AnthropicProvider`/`anthropic.Anthropic`
      to their new module paths). `processor.py` did not import `llm_parser` — nothing to update
      there. Also fixed a stale doc pointer in `tests/fixtures/README.md`.
      Squash-merged to `refactor/split-extraction` · commit `63761c4` · 2026-08-01.
      Suite: 372 passed, 0 skipped, 0 failed. E2E smoke-tested `traininglogs validate --parser
      rules` against a real fixture; all new/renamed modules import cleanly.
      Known pre-existing, out-of-scope breakage: untracked `scripts/spot_check_ai_parser.py`
      still imports the deleted `llm_parser` module — left as-is per the standing decision that
      it's unrelated to this thread (Apoorva to commit or discard it separately).
- [x] **2. Parametrize the providers** (no behavior change). `ExtractionProvider.extract()` now
      takes `system_prompt`, `tool_name`, `tool_description` as arguments; `providers.py` no
      longer hardcodes `SYSTEM_PROMPT`/`"extract_workout"`. New `TOOL_NAME`/`TOOL_DESCRIPTION`
      constants in `extraction.py`; `llm_extract_validator.py` (the correction path, not called
      out in the original blast-radius table but also a caller of `.extract()`) updated to pass
      the same values through explicitly. Updated stub `extract()` signatures in 4 test files.
      Added `TestProviderParametrization` to lock in real pass-through (not just a rename).
      Squash-merged to `refactor/split-extraction` · commit `9c50992` · 2026-08-01.
      Suite: 374 passed, 0 skipped, 0 failed.
- [x] **3. Small schemas + focused prompts.** Added `SessionShellExtract`, `ExerciseExtract`,
      `ExercisePosition`/`ExerciseSplit` to `schemas.py` (date validator factored into a shared
      `_validate_date()` helper, matching the existing `_validate_rpe()` convention in
      `models.py`). Added `SPLITTER_SYSTEM_PROMPT`, `SHELL_SYSTEM_PROMPT`,
      `WORKER_SYSTEM_PROMPT` to `prompts.py` — worker reuses `MOVEMENT_SKILL_CONVENTIONS`
      verbatim. `SYSTEM_PROMPT` itself left completely untouched (byte-for-byte verified) so
      the monolithic path stays reachable for comparison, per Step 8.
      New tests: `test_agent_schemas.py` (valid construction, each validator, JSON round-trip
      per class), `test_agent_prompts.py` (structural guard tests, same spirit as the existing
      `TestSystemPromptSessionNotesAndRemarks`). Nothing wired up yet — that's Steps 4-5.
      Squash-merged to `refactor/split-extraction` · commit `5a22fd1` · 2026-08-01.
      Suite: 405 passed, 0 skipped, 0 failed.
- [x] **4. The three small-call functions.** `segment(text) -> ExerciseSplit`,
      `extract_shell(text) -> SessionShellExtract`, `extract_exercise(text, position) ->
      ExerciseExtract` added to `extraction.py`, each wired to its Step 3 prompt/schema with
      its own tool name/description constants. `extract_exercise()` builds its own prompt
      ("Extract exercise number N" + full text) rather than depending on any other call having
      run — decision 7 enforced by the function signature itself (only `text`/`position`/
      `provider`) and tested directly (`test_self_contained_no_call_ordering_dependency`).
      Not wired into anything yet — that's Step 5.
      Squash-merged to `refactor/split-extraction` · commit `4ef81de` · 2026-08-01.
      Suite: 418 passed, 0 skipped, 0 failed.
- [x] **5. The assembler.** `assemble(text, provider)` in `extraction.py`: segment() → shell()
      → one `extract_exercise()` per position (sequential) → glued into a
      `TrainingLogLLMExtract`. Worker `uncertain_fields` (relative dot-paths) get prefixed to
      `exercises.{index}.…` to match the monolithic convention; shell `uncertain_fields` pass
      through unprefixed. Failed worker → flagged placeholder `Exercise` (name from the
      splitter, failure noted in `notes`) + an entry in a new `warnings` field.
      **Open item resolved (2026-08-01, confirmed with Apoorva):** warnings live in their own
      `warnings: List[str]` field on `TrainingLogLLMExtract`, separate from `uncertain_fields`
      — `uncertain_fields` is the LLM's self-reported doubt about something it did extract;
      `warnings` is the deterministic drop-check's "we think this is actually wrong."
      Tests in `test_agent_assembler.py`: gluing/ordering, uncertain-field prefixing (both
      directions), failed-worker-becomes-placeholder, and a regression test built from the
      real 6-exercise `programmed_push_pull_session_with_remarks.md` fixture (the file that
      originally exposed the drop bug) asserting all 6 exercises and each one's last-set RPE
      survive the assembler.
      Squash-merged to `refactor/split-extraction` · commit `34b8738` · 2026-08-01.
      Suite: 423 passed, 0 skipped, 0 failed.
- [x] **6. Drop-check.** `audit(text, split, exercises)` in `extraction.py`: exercise-count
      match (defensive invariant) + orphaned RPE/weight-shaped token scan → list of warnings,
      wired into `assemble()`. Weight scan is kg-only by design (lbs is unit-converted before
      landing in `weight_kg`, so scanning for it would always false-positive); RPE ranges
      check the upper bound to match the extraction convention. Updated the Step 5 regression
      test's fake data to use the real fixture's actual weights (was a flat 90kg placeholder)
      so the full `assemble()`+`audit()` round trip on it now produces zero warnings.
      `test_agent_drop_check.py`: count-mismatch and token-scan true/false cases in isolation.
      Squash-merged to `refactor/split-extraction` · commit `111c9af` · 2026-08-01.
      Suite: 434 passed, 0 skipped, 0 failed.
- [ ] **7. Card surfacing.** Show warnings and failed-exercise placeholders on the confirmation
      card. Update card builder + renderer + their tests.
- [ ] **8. Wire into the orchestrator.** Make the assembler the AI-parser default; keep the
      monolithic path reachable behind a flag/env for comparison. Update orchestrator + CLI
      tests. E2E on the real 6-exercise fixture with a live model.
- [ ] **9. Docs.** `CHANGELOG.md` `[Unreleased]` entry; update `docs/design.html` system-shape
      + data-flow section (bump eyebrow/footer date by hand).

## Open items to settle during, not blocking the plan

- Where warnings live on `TrainingLogLLMExtract` — RESOLVED at Step 5: separate `warnings`
  field.
- Exact regex set for RPE-shaped / weight-shaped tokens — RESOLVED at Step 6 (kg-only, narrow
  by design). Grow the patterns later from real misses, not preemptively.

## ▶ Resume here

Steps 0-6 done on `refactor/split-extraction` (commit `111c9af`), suite green (434 passed,
0 skipped, 0 failed). All core split-extraction logic is now built and tested with fake
providers — no live LLM calls have been made yet. Next: Step 7 — card surfacing. Show
`warnings` and failed-exercise placeholders on the confirmation card: update
`validation_card_builder.py` + `renderer.py` + their tests. Cut
`refactor/split-extraction-card-surfacing` from `refactor/split-extraction`.

**Note for Step 8** (wiring into the orchestrator + live E2E on the real 6-exercise fixture):
that step makes real Anthropic/Groq API calls and changes the AI-parser's default behavior —
pause and confirm with Apoorva before running it, same as any step that spends API credits or
changes default runtime behavior.
