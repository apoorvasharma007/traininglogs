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
- [x] **7. Card surfacing.** `UserValidationCard.warnings`, `ExerciseHeader.failed`,
      `ExerciseCard.failure_reason` (full text — `note_preview` suppressed for a failed
      exercise instead of a truncated duplicate). Builder detects a placeholder exercise via
      `PLACEHOLDER_NOTE_PREFIX` (now exported from `extraction.py`, shared with
      `_placeholder_exercise()`) rather than adding a synthetic field to the `Exercise` model
      — that model's blast radius extends well beyond this confirmation flow.
      `TerminalRenderer` prints warnings (⚠, bold yellow) after the session header and renders
      a failed exercise as a red "⚠ EXTRACTION FAILED" header + reason, skipping the empty
      warmup/sets sections a placeholder would otherwise render.
      Squash-merged to `refactor/split-extraction` · commit `ff871dd` · 2026-08-01.
      Suite: 444 passed, 0 skipped, 0 failed.
- [~] **8. Wire into the orchestrator.** Make the assembler the AI-parser default; keep the
      monolithic path reachable behind a flag/env for comparison. Update orchestrator + CLI
      tests. E2E on the real 6-exercise fixture with a live model.

      **In progress — live E2E findings and design work (2026-08-01), via Groq/llama-3.3-70b:**

      - Orchestrator wiring done: `LLMOrchestrator` defaults to `assemble()`;
        `use_monolithic_parser` (constructor arg + `TRAININGLOGS_USE_MONOLITHIC_PARSER` env var)
        falls back to `parse()`. `test_agent_llm_orchestrator.py` updated (existing tests
        exercise the confirm/correct/render loop mechanics via the monolithic path since those
        mechanics don't depend on which extraction path produced the initial extract; new
        `TestLLMOrchestratorDefaultsToSplitExtraction` covers the default path + the escape
        hatch). Suite: 448 passed.

      - **Live run 1 (crash):** `ExerciseExtract` was `{exercise: Exercise, uncertain_fields}`
        (nested). Groq's model flattened it anyway — a known tool-calling tendency for
        single-nested-object schemas, confirmed by industry guidance (deep/nested schemas
        measurably increase failure rates; flat is the documented best practice). **Fixed**:
        `ExerciseExtract` now extends `Exercise` directly (flat), `assemble()` strips the extra
        field back to a plain `Exercise` via `model_dump(exclude={"uncertain_fields"})`. Suite:
        449 passed (added `test_schema_is_flat_not_nested` guard).

      - **Live run 2 (ran, wrong data):** 3 of 6 exercises got zero working sets; one exercise
        ("Lat Pulldown") was extracted twice while another ("Triceps Pushdown") was dropped
        entirely. The drop-check (Step 6) correctly flagged all of it via warnings — nothing
        silently lost — but extraction accuracy itself was the problem. Root cause: each
        worker call re-reads the *entire* document and must recount to the Nth exercise block
        itself, every time — a textbook "lost in the middle" failure (LLMs are measurably worse
        at locating content in the middle of a long, repetitive document — confirmed via
        research, not just guessed). Prompt strengthening alone (explicit block-counting
        instructions, explicit "sets is required") was applied but not sufficient by itself —
        see run 3.

      - **Live run 3 (crash, different cause):** Groq rejected a call because the model wrote
        `rep_count: 15` (bare int) for a *working* set, confusing it with `warmup_sets.rep_count`
        (which genuinely is a bare int in our schema). Separately surfaced a structural gap:
        neither provider's retry loop catches `groq.BadRequestError`/`anthropic.BadRequestError`
        (the SDK's own server-side schema rejection) — only *our* post-hoc Pydantic validation
        failures get the existing 2-attempt reask/retry budget. This is the standard "reask"
        pattern (used by Guardrails AI and Instructor) applied to a failure class we weren't
        catching. Not yet fixed — tracked as a follow-up, see below.

      **Design decision locked (2026-08-01, discussed with Apoorva): deterministic pre-chunking.**
      Root-causing run 2 above led to research on how real extraction pipelines handle "pull N
      similar items out of one long document" reliably — the standard answer is the map-reduce
      pattern: chunk the document with plain code *once*, hand each worker only its own isolated
      slice, never the whole document. Rejected pure regex/format-based chunking outright — this
      project's AI parser exists specifically because the input contract is deliberately
      free-text with no required format (TRACK B decision), so regex-chunking on assumed
      structure would reintroduce the old rules-parser's brittleness for a different job.

      Chosen approach — hybrid, grounded chunking:
      - `segment()`'s schema (`ExercisePosition`) gains a new field: `anchor` — a verbatim quote
        of the line that begins that exercise's block in the source text. Explicitly prompted
        as "copy exactly, do not correct spelling/casing/formatting" — deliberately NOT reusing
        `name`, because `name` is the cleaned/canonical label (the prompt already tells the
        model to strip set/rep/weight detail from it) and cleaning is exactly what makes a
        string unreliable as a literal `text.find()` target.
      - Anchors are located **sequentially** — `text.find(anchor, start=end_of_previous_anchor)`,
        not a global search — searching forward from where the previous exercise's anchor was
        found. This is what actually neutralizes repeated-text ambiguity (e.g. the same exercise
        name appearing twice, which is allowed and was the exact shape of run 2's duplicate-
        exercise bug): a longer/smarter anchor string doesn't help if two exercises share it, but
        searching in split order from where we already are does, using ordering information we
        already trust.
      - Chunk boundaries: each chunk runs from its own anchor to a few lines past the *next*
        located exercise's anchor (small trailing overlap for safety, confirmed with Apoorva),
        or to end-of-document for the last exercise.
      - Fallback: if an anchor isn't found verbatim (model paraphrased despite instructions),
        that one exercise's chunk is skipped and `assemble()` falls back to today's behavior
        (full text + position) for just that worker, with a warning noting the fallback — same
        graceful-degradation spirit as the existing failed-worker-becomes-placeholder path.
        Never crash, always degrade and flag.
      - Side effect: `assemble()` now deterministically overrides `exercise.number = position`
        after each worker call (we already know the correct position from the split; no reason
        to trust the model's own reported number field once we can just set it).
      - Not yet implemented — this is the next unit of work before re-attempting the live E2E
        check.

      **Deferred, not blocking this fix:** the retry-loop gap (run 3) — catching
      `BadRequestError` in both providers and reasking with the specific schema-violation
      message, same mechanism as today's existing retry-on-our-own-validation-failure path.
      Revisit after chunking is verified live, since chunking may also reduce how often the
      model produces a malformed call in the first place (smaller, simpler input per call).
- [ ] **9. Docs.** `CHANGELOG.md` `[Unreleased]` entry; update `docs/design.html` system-shape
      + data-flow section (bump eyebrow/footer date by hand).

## Open items to settle during, not blocking the plan

- Where warnings live on `TrainingLogLLMExtract` — RESOLVED at Step 5: separate `warnings`
  field.
- Exact regex set for RPE-shaped / weight-shaped tokens — RESOLVED at Step 6 (kg-only, narrow
  by design). Grow the patterns later from real misses, not preemptively.

## ▶ Resume here

Steps 0-7 done on `refactor/split-extraction` (commit `ff871dd`), suite green (444 passed,
0 skipped, 0 failed). All core split-extraction logic and its confirmation-card surfacing are
built and tested with fake providers — no live LLM calls have been made yet.

**Next: Step 8 — wire into the orchestrator + live E2E on the real 6-exercise fixture.**
This step makes real Anthropic/Groq API calls (costs money, hits external services) and
changes the AI-parser's default behavior (`assemble()` becomes the default instead of
`parse()`). **Pause and confirm with Apoorva before running it** — same bar as any step that
spends API credits or changes default runtime behavior. Cut
`refactor/split-extraction-wire-orchestrator` from `refactor/split-extraction` once approved.
