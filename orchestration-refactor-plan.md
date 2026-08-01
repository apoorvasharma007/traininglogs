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
      **Fixed 2026-08-01** (see below, unblocked earlier than planned since it turned out to
      be cheap and independent of the chunk-leak bug).

      **Correction (2026-08-01): the "lost in the middle" diagnosis for run 2 above was wrong.**
      After pre-chunking was implemented and live-tested (against both `llama-3.3-70b-versatile`
      and, once its daily quota was exhausted from testing, `openai/gpt-oss-120b`), the *exact*
      same failure shape kept recurring: first and last exercise always correct, all four middle
      exercises wrong/empty/failed, reproducibly across runs and across both models — including
      one live run reproducing the *identical* wrong name at the same position twice, and a
      model refusal quoting verbatim that its excerpt "contains only two main working-exercise
      blocks." That specificity didn't fit a genuine model-reliability story, so before
      finishing Step 8, Apoorva asked for a documented research prompt on whether "lost in the
      middle" (a long-context phenomenon) could even apply to a ~1,080-token splitter call —
      it doesn't; that's well below where the effect has been empirically studied. External
      research (a separate AI research session) then root-caused the real bug precisely, which
      was verified directly against actual chunk output before accepting it:

      `CHUNK_TRAILING_OVERLAP_LINES = 3` (the "safety margin" from the design decision above)
      meant every non-last chunk contained a leaked fragment of the *next* exercise (its name +
      first warmup line) in addition to the current one, and `extract_exercise()` was called
      with the *global* split position against that now-2-exercise excerpt. A worker told
      "extract exercise number 3" when handed a chunk containing only 2 recognizable blocks has
      no correct answer — it picks the wrong (leaked) block, refuses as out-of-range, or returns
      empty/garbage. This reproduces every cell of every observed failure table exactly,
      including the verbatim refusal and the reproducible wrong name (the leaked fragment's own
      name, which has no Sets: section since it's cut off mid-exercise). First/last were never
      positionally special — index 1 coincidentally equals chunk-local index 1, and the last
      chunk has no next exercise to leak from. **None of LITM, MoE routing, Groq's tool-calling
      reliability, gpt-oss-120b vs. llama, or the anchor schema's 3 required fields were
      necessary to explain any of it** — a correct splitter feeding a broken chunker produces
      the identical failure regardless of model. This also means the splitter itself was never
      shown to be unreliable in any of these runs; `assemble()` only ever overrides `number`
      from the split, not `name`, so the wrong names observed were worker output, not splitter
      output.

      **Fix applied** (commit `21e948a`): `CHUNK_TRAILING_OVERLAP_LINES` set to 0 (a chunk
      already runs up to the next exercise's own anchor line, and everything belonging to the
      current exercise — including its trailing remarks — sits before that line by
      construction, so a positive value only ever leaks, never protects a real case); and
      `assemble()` now passes position 1, not the global split position, to `extract_exercise()`
      whenever a chunk was successfully isolated (global position is only meaningful — and only
      still used — on the full-text fallback path). Test doubles updated to match (see commit).
      Suite: 467 passed, 0 skipped, 0 failed. **Not yet re-verified live** — that's next.
- [ ] **8.5. DETOUR — per-call prefix cost.** *Step 8 is paused here, not abandoned. The live
      E2E runs above cannot be repeated often enough to finish Step 8 without first fixing what
      each call costs. Do this step, then return to Step 8 and re-run the live E2E.*

      **The problem.** The split-call design trades one big call for N+2 small ones, and every
      one of them re-sends its entire system prompt *and* its entire tool schema from scratch —
      there is no continuation between calls on either provider's API. Measured on the current
      branch (estimated at ~3.7 chars/token; to be confirmed with `count_tokens` in sub-step a):

      | Call | System prompt | Tool schema | Prefix per call |
      |---|---|---|---|
      | Splitter | 1,320 ch | 1,018 ch | ~630 tok |
      | Shell | 2,472 ch | 2,472 ch | ~1,340 tok |
      | Worker | 7,298 ch | 8,374 ch | ~4,240 tok |

      A 6-exercise session therefore spends ~27,400 tokens on *prefix alone* (630 + 1,340 +
      4,240 × 6), before a single character of workout text. Against Groq's free-tier 100K
      tokens/day cap for `llama-3.3-70b-versatile` that is ~3.6 sessions/day, which matches the
      observed burn during runs 1-3 above.

      **Two findings that reframe the problem:**

      - **The tool schema is 53% of the worker prefix — larger than the prompt.** 8,374 ch of
        serialized `ExerciseExtract.model_json_schema()` vs 7,298 ch of `WORKER_SYSTEM_PROMPT`.
        Any cost work that looks only at prompt text is optimizing the smaller half. Note this
        also means the flat-schema fix from run 1 and the pre-chunking work above both *added*
        per-call prefix; that was the right call for accuracy, but it has a price.
      - **Trimming prompt content is not on the table.** Every rule in `WORKER_SYSTEM_PROMPT`
        was added to fix a specific extraction bug found in live testing (the `rep_count`
        shape rule from run 3 is the clearest example). Cutting content to cut tokens would
        reintroduce those bugs. The prefix has to stay and be paid for differently.

      **Locked decision: prompt caching, not prompt trimming.** Both providers cache a repeated
      prompt *prefix* across separate calls; the worker prefix is byte-identical across all N
      worker calls, so calls 2..N can read it instead of re-sending it. Groq's caching is
      automatic (50% discount, and cached tokens **do not count toward rate limits** — the part
      that actually matters for the TPD cap); Anthropic's is explicit via `cache_control`.

      **Rejected: hoisting a shared document into the cached prefix.** Considered ordering each
      worker request as `[tools] → [system] → [document] → [per-exercise instruction]` so the
      session text caches too. Does not apply — `_chunk_exercises()` (Step 8 above) already
      gives each worker its *own isolated slice*, so there is no shared document across worker
      calls to hoist. Recorded here so it isn't re-proposed later; it would only become relevant
      if pre-chunking were ever reverted.

      **Prefix-ordering audit — clean, no restructuring needed.** `providers.py` already sends
      `tools` → `system` → `messages`; `WORKER_SYSTEM_PROMPT` and the tool schema are
      byte-identical across workers; `_reask_message()` appends retries at the *end* so the
      retry path doesn't disturb the prefix. The ~4,240-token block is cacheable as-is.

      **Two things block caching from working at all:**

      - `providers.py:66` passes `system=system_prompt` as a plain string. A string cannot carry
        `cache_control` — it has to become a list of text blocks.
      - `DEFAULT_ANTHROPIC_MODEL` (`providers.py:10`) is `claude-haiku-4-5`, whose **minimum
        cacheable prefix is 4,096 tokens**. The worker prefix estimates at ~4,240 — over the line
        by ~3%, which is inside the estimation error. Below-minimum prefixes fail **silently**
        (`cache_creation_input_tokens: 0`, no error), so on Haiku 4.5 we would be one prompt edit
        away from the cache switching itself off with no signal. Sonnet 5 (1,024 min) and Opus 5
        (512 min) have real headroom; Groq's GPT-OSS models (128-1,024) clear it easily.

      Sub-branch `refactor/split-extraction-token-cost` from `refactor/split-extraction`.

      - [ ] **a. Measure.** Script reporting exact `count_tokens` for all three prefixes on the
            target model, replacing the estimates in the table above. Settles the Haiku-4.5
            4,096-token question with a number. **Spends API credits (one cheap call per
            prefix) — confirm before running.**
      - [ ] **b. Make the prefix cacheable.** `AnthropicProvider.extract` takes `system` as a
            block list with `cache_control: {"type": "ephemeral"}`. Hoist the three
            `model_json_schema()` calls (`extraction.py:42,57,72,92`) to module-level constants
            so the schema is provably one stable object rather than regenerated per call.
      - [ ] **c. Verify.** Assert `cache_read_input_tokens > 0` on workers 2..N against the real
            6-exercise fixture, and log the per-session prefix total. This is the pass/fail gate
            for the whole step — a silent cache miss must fail loudly here rather than in
            production. **Spends API credits — confirm before running.**
      - [ ] **d. Decide on the Groq path.** Groq caching currently covers only the GPT-OSS
            models, **not** `llama-3.3-70b-versatile`. Moving the worker call to
            `openai/gpt-oss-120b` would double the free-tier cap (200K vs 100K TPD) *and* take
            the cached prefix off the meter entirely. Gated on a tool-calling reliability check
            first — there are open reports of `gpt-oss-120b` on Groq mishandling `json_schema`
            and emitting free-form text instead of a tool call, which is precisely the failure
            class this whole refactor exists to eliminate. Do not adopt on cost grounds alone.

      **The retry-loop `BadRequestError` gap from run 3 was fixed** (commit `978fa38`, both
      providers now reask on the SDK's own schema-rejection error) — done ahead of this step
      since it turned out cheap and unblocking it didn't depend on anything here.

      **Blocked on `ANTHROPIC_API_KEY`.** Sub-step (a) was attempted and failed: `401 invalid
      x-api-key` — the same dead key flagged in earlier-session memory, still unresolved.
      Since Groq's caching only covers GPT-OSS models (not the `llama-3.3-70b-versatile`
      currently in use) and Apoorva has ruled out paid models entirely for this project, this
      whole step is Anthropic-dependent and stalled until the key is rotated. Not pursued
      further for now — see the chunk-leak fix below, which took priority.
- [ ] **9. Docs.** `CHANGELOG.md` `[Unreleased]` entry; update `docs/design.html` system-shape
      + data-flow section (bump eyebrow/footer date by hand).

## Open items to settle during, not blocking the plan

- Where warnings live on `TrainingLogLLMExtract` — RESOLVED at Step 5: separate `warnings`
  field.
- Exact regex set for RPE-shaped / weight-shaped tokens — RESOLVED at Step 6 (kg-only, narrow
  by design). Grow the patterns later from real misses, not preemptively.

## ▶ Resume here

Steps 0-7 done on `refactor/split-extraction` (commit `ff871dd`), suite green (444 passed,
0 skipped, 0 failed). Step 8 (orchestrator wiring, live E2E, chunk-leak fix) and the retry-loop
fix are both done on `refactor/split-extraction-token-cost` (commits `d3fbe71`, `978fa38`,
`d76c1b9`, `21e948a` — branched off `refactor/split-extraction-wire-orchestrator`, which itself
branched off the base; not yet squash-merged anywhere, this whole line of work is still mid-flight).
Suite: 467 passed, 0 skipped, 0 failed.

**Current state, plainly:**
- Orchestrator defaults to `assemble()`; `parse()` reachable via flag/env for comparison.
- Both providers reask on `BadRequestError`, not just our own post-hoc validation failures.
- Pre-chunking is implemented, and the chunk-leak + local/global position bug that was
  producing every observed "model reliability" failure across ~5 live E2E runs (2 models) is
  fixed — **but not yet re-verified live**. That's the immediate next action.
- Step 8.5 (token cost via prompt caching) is blocked on a dead `ANTHROPIC_API_KEY` and is
  lower priority than re-verifying accuracy — no point optimizing cost on a path we haven't
  confirmed actually works yet.
- Free models only, confirmed with Apoorva — paid models (Anthropic once the key works, or
  otherwise) are off the table for this project regardless of reliability tradeoffs.
- `llama-3.3-70b-versatile`'s Groq free-tier quota (100K TPD) has been exhausted multiple times
  today from live testing; `openai/gpt-oss-120b`'s separate 200K TPD quota is untouched and
  available right now.

**Next action: re-verify the chunk-leak fix live**, using the already-built comparison script:
```
.venv/bin/python scripts/validate_with_model.py \
  tests/fixtures/valid/programmed_push_pull_session_with_remarks.md --model openai/gpt-oss-120b
```
Expect (if the fix holds): all 6 exercises present in order, each with its own sets/warmup
populated, no cross-exercise leakage, and no more of the specific failure signatures from the
pre-fix runs (wrong name at position 2, the "only two blocks" refusal, empty names/args at
positions 3-5). Run it a couple of times for a real sample — one clean run isn't enough
evidence either way, per the false confidence a single early spot-check gave the first time.
Once accuracy is confirmed reliable(-enough) for a free model, decide: finish Step 8 as
originally scoped (pick a default free model, document its known residual limitations, rely on
the confirmation card — Apoorva's earlier "option 3"), or revisit Step 8.5 if cost still
matters once accuracy is no longer the open question.
