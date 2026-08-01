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

- [ ] **0. Base branch + this plan.** Cut `refactor/split-extraction` from `dev`, commit this file.
- [ ] **1. Split the file into cohesive modules** (pure move, no behavior change). Break
      `llm_parser.py` into `schemas.py` (the extract models), `prompts.py` (system prompts),
      `providers.py` (`ExtractionProvider` + Anthropic/Groq), and `extraction.py` (`parse()`
      today; the new brains later). Update imports in `llm_orchestrator.py`, `processor.py`,
      and the five test files. Suite stays green — this is the gate that proves the move was
      clean before any new logic lands.
- [ ] **2. Parametrize the providers** (no behavior change). Let `extract()` take the system
      prompt + tool name/description as arguments instead of the hardcoded module constants,
      so the same provider can serve the splitter, shell, and worker calls. Monolithic path
      keeps working by passing today's prompt. Suite stays green.
- [ ] **3. Small schemas + focused prompts.** Add `SessionShellExtract` (everything except
      `exercises`), `ExerciseExtract` (one `Exercise` + its own `uncertain_fields`), and a
      splitter schema (ordered list of `{position, name}`). Write the three focused system
      prompts (splitter / shell / worker — worker reuses the movement-skill conventions).
      Unit tests: valid construction, each validator, `model_dump(mode="json")` round-trip.
- [ ] **4. The three small-call functions.** `segment(text)`, `extract_shell(text)`,
      `extract_exercise(text, position)` — each a pure function tested with a fake provider.
      This is where decision 7 (self-contained workers) is enforced and tested.
- [ ] **5. The assembler.** Run splitter → shell → one worker per position (sequential) →
      glue into a `TrainingLogLLMExtract`. Failed worker becomes a flagged placeholder
      exercise. Integration test with a fake multi-exercise provider; add a regression test
      built from the real 6-exercise session that reproduced the drop bug (assert all 6
      exercises and their RPEs/remarks survive).
- [ ] **6. Drop-check.** Deterministic audit: exercise-count match + orphaned RPE/weight-shaped
      token scan → list of warnings. Unit-test the regex/audit in isolation (false-positive
      and false-negative cases).
- [ ] **7. Card surfacing.** Show warnings and failed-exercise placeholders on the confirmation
      card. Update card builder + renderer + their tests.
- [ ] **8. Wire into the orchestrator.** Make the assembler the AI-parser default; keep the
      monolithic path reachable behind a flag/env for comparison. Update orchestrator + CLI
      tests. E2E on the real 6-exercise fixture with a live model.
- [ ] **9. Docs.** `CHANGELOG.md` `[Unreleased]` entry; update `docs/design.html` system-shape
      + data-flow section (bump eyebrow/footer date by hand).

## Open items to settle during, not blocking the plan

- Where warnings live on `TrainingLogLLMExtract`: reuse `uncertain_fields`, or add a separate
  `warnings` field? (Leaning separate — different meaning: "we think this is wrong" vs "we're
  unsure." Decide at step 5.)
- Exact regex set for RPE-shaped / weight-shaped tokens (step 5). Start narrow, grow from real
  misses.

## ▶ Resume here

Plan drafted and awaiting Apoorva's review. Nothing branched or coded yet. Next action once
approved: execute Step 0 — cut `refactor/split-extraction` from `dev` and commit this file.
