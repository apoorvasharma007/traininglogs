# Extraction accuracy plan

## Goal and motivation

One live run of the split-extraction pipeline against
`tests/fixtures/valid/programmed_push_pull_session_with_remarks.md` produced three value-level
errors on `openai/gpt-oss-120b` at `temperature=0`, on clean single-exercise excerpts: weight
dropped from all three Incline DB Press sets plus its whole warmup section; the Lat Pulldown
exercise-level RPE attached to set 1 instead of set 3; and the Lateral Raise working sets
routed into `warmup_sets`, leaving `sets` empty. All three were schema-valid, so no retry
fired, and `audit()` caught at most one of them.

Every one of those errors is in content the input format specifies deterministically
(`1. 80kg x 8`). None are in the fields that actually need a language model (`tags`,
`modality`, `movement_pattern`, `notes`). We have a deterministic line-parser,
`DeepTrainingParser` (`parser/parse.py`), already tested and in production for a separate
ingestion path, that parses these lines correctly 100% of the time.

This plan does **not** cover: the chunk-leak bug (fixed in `21e948a`), token cost /
prompt caching (separate branch), or migrating to Groq `response_format` structured outputs
(constrained decoding guarantees shape, not values — it would not have caught any of the three).

## Architecture (revised 2026-08-01, second pass)

A first draft of this plan called the LLM for the full exercise every time and reconciled its
output against the parser afterward, overwriting disagreements. That was rejected: it asks the
LLM to do work it doesn't need to do, then arbitrates after the fact — patch-shaped, not
architecture-shaped, and the "merge notes by set number when counts match" arbitration logic was
already growing edge cases (see git history on this file for that version).

**Locked instead: parse first, ask second.**

- `parse_exercise_block(chunk_text)` runs *before* the worker call, not after. It is a binary,
  all-or-nothing gate: every enumerated line under every header (`Warmup:`, `Sets:`) must parse,
  or it returns `None`. No partial parses — that's how the old reconciler crept back in.
- **Parser succeeds** → the worker is never shown a job it doesn't need to do. It's called with
  a *narrow* schema (`ExerciseLabelsExtract`, no `sets`/`warmup_sets` fields at all) and given the
  parsed set indices as read-only context. Its only job: `name`, `tags`, `modality`,
  `movement_pattern`, exercise-level `notes`/`form_cues`/`target_muscle_groups`/`rep_tempo`/
  `current_goal`, and per-set notes keyed to the indices it was handed. `sets` and `warmup_sets`
  on the final `Exercise` are built directly from the parser's output — the LLM's schema
  structurally cannot corrupt them, because it was never asked for them.
- **Parser fails** (irregular format — calisthenics, timed holds, band-assisted reps) → the
  worker gets the full `ExerciseExtract` schema and does the whole job itself, exactly as today.
  Nothing changes for this path; it's the existing behavior, untouched.
- A note keyed to a set index the parser didn't produce is dropped with a warning, not treated
  as a hard failure — low-stakes field, no retry loop needed for it.
- Exercise-level RPE placement (apply to the *last* set) is **not** structurally fixed by this —
  it's still a judgment call the LLM makes, just against a known index list instead of a list it
  invented itself. The prompt rule for it stays. Don't oversell this as a three-for-three fix:
  only the weight-drop and section-misfile failures are structurally impossible after this; the
  RPE-placement failure is reduced-risk, not eliminated.
- `audit()` gains one new mechanical check, independent of which path was used: the count of
  enumerated lines under `Warmup:`/`Sets:` in the source must equal
  `len(sets) + len(warmup_sets)` in the output. On the parsed path this is trivially guaranteed
  by construction; on the fallback path it's a real, new check. No LLM involved in `audit()`,
  same as today.

**Explicitly rejected, with reasoning (research session, 2026-08-01):**

- *Reconcile-after (the first draft of this plan).* Superseded by parse-first, not layered
  under it.
- *Expose the parser to the model as a tool it can choose to invoke.* "Is this block regular
  enough for the parser" is a 100%-decidable question in code (`parsed is not None`) — it's a
  perfect oracle. Routing that decision through the model trades a perfect oracle for a
  probabilistic one for no offsetting benefit, and adds latency, nondeterminism, and rate-limit
  exposure our free-tier constraint can't absorb.
- *LLM-based self-verification pass.* Evidence-based no: same-model self-correction without an
  external signal doesn't reliably work and can degrade correct answers (Huang et al., "Large
  Language Models Cannot Self-Correct Reasoning Yet," ICLR 2024,
  arXiv:2310.01798; "Are You Sure?", arXiv:2311.08596). The parser *is* the external verifier
  this literature says you need — parse-first applies it before the error can be made rather
  than after, which is strictly better than applying it after. Anthropic's own distinction
  ("Building Effective Agents": workflows are predefined code paths orchestrating LLMs and
  tools; agents are LLMs dynamically directing their own process) also means this pipeline was
  always a workflow, not an agent, by its own definition — parse-first doesn't change that
  classification, it just adds one more gate to a workflow that already had several.
- **"Agentic" is not a design goal to optimize against reliability here.** Flexibility for
  irregular input is the reason the LLM is in the pipeline at all, and parse-first fully
  preserves it — an unparseable block still goes down the exact full-LLM path it does today.
  What's removed is the LLM's license to get `30kg x 8` wrong on the regular-format common case.

## Decisions locked (2026-08-01)

- **Ownership:** parser owns the numeric spine (`sets[].number/weight_kg/rep_count`,
  `warmup_sets`) whenever it can fully parse a block; LLM owns classification, free text, and
  (still, as a judgment call) RPE placement.
- **Call count:** keep one LLM call per exercise. No change to the number of API calls per
  session.
- **`reasoning_effort`:** not set. Groq's default (`medium`) is used implicitly; no code change.
- **Step 4 (originally "experiments"), folded into Step 2:** the reasoning_effort experiment is
  dropped (see above); the two live-fixture experiments (Lat Pulldown with distinguishable sets,
  Lateral Raise without the dangling `Warmup:` line) become Step 2's end-to-end regression
  fixtures rather than a separate step, since parse-first makes their outcomes structurally
  determined rather than something to empirically probe.
- **`WorkingSet` / `Exercise` field reordering:** dropped (unchanged from first draft) — aimed
  at the RPE misplacement, which isn't a field-order problem.

## Blast radius / audit

Touched:

| File | Change |
|---|---|
| `src/traininglogs/parser/parse.py` | warmup regex accepts a `kg`/`lbs` unit; four line parsers promoted to module-level functions with the methods kept as delegates |
| `src/traininglogs/agent/exercise_block.py` | **new** — block splitter returning `ParsedBlock \| None` |
| `src/traininglogs/agent/schemas.py` | **new** `ExerciseLabelsExtract` — narrow schema, no `sets`/`warmup_sets` |
| `src/traininglogs/agent/extraction.py` | `assemble()`'s worker loop branches on `parse_exercise_block()` outcome *before* calling the worker; new `extract_exercise_labels()` alongside existing `extract_exercise()`; `audit()` gains the line-count check |
| `src/traininglogs/agent/prompts.py` | new, small `LABELS_SYSTEM_PROMPT` for the narrow path; existing `WORKER_SYSTEM_PROMPT` **unchanged** — it still has to teach full extraction for the irregular-format fallback path |
| `tests/test_agent_exercise_block.py` | **new** |
| `tests/test_agent_assembler.py` | scripted worker payloads and dispatch updated for the two-path branch |

Explicitly untouched: DB schema, DB column names, Pydantic field names on `Exercise`/
`WorkingSet`, the `TrainingMarkdownParser` markdown path, `_chunk_exercises`, `segment()`,
`extract_shell()`, the number of API calls per session, `WORKER_SYSTEM_PROMPT`'s content (it's
needed as-is for the fallback path).

Known breakage to expect:

1. `tests/test_agent_assembler.py:77` — `SAMPLE_TWO_EXERCISE_TEXT` contains parseable `Sets:`
   lines, so the parsed path now fires for it. The scripted provider needs a labels-schema
   payload for that exercise, not a full `ExerciseExtract` payload — this is a bigger fixture
   change than the reconcile-after draft would have needed, not a smaller one. Fix the fixtures;
   do not weaken the assertions.
2. Step 2 changes extraction output for existing sessions. Historical regeneration is its own
   branch per `.claude/regen-historical.md` — not bundled here.
3. Step 2 will start emitting warnings on real sessions that pass silently today (the new
   line-count check). That is the intent; expect triage noise before it gets quiet.

## Safety property

`parse_exercise_block` is **all-or-nothing per block**: if any line under `Sets:` fails to
parse, it returns `None` and the LLM owns that block entirely via the unchanged
`ExerciseExtract`/`WORKER_SYSTEM_PROMPT` path, exactly as today. There is no half-deterministic,
half-LLM set list, and no path where the LLM's own `sets`/`warmup_sets` output can compete with
the parser's — on the parsed path it's never asked for them at all. This is what guarantees the
calisthenics, rings, and timed-hold formats (`18s - tuck, clean`, `5 attempts, 2 clean -
band-assisted`) cannot regress.

## Steps

Base branch `fix/extraction-accuracy` off `dev`. One sub-branch per step, squash-merged back.
Suite fully green (0 failed, 0 skipped) before each squash-merge.

### - [x] Step 1 — Wire up the existing parser (`fix/extraction-accuracy-parser-reuse`) — done, squash-merged as `f063ef3`

No pipeline behavior change. Nothing calls the new module yet. Unaffected by the
reconcile-after → parse-first revision above — this step only builds the parsing capability.

- [x] `_parse_warmup_set_line` regex `([\d.]+)\s*x` → `([\d.]+)\s*(?:kg|lbs?)?\s*x`.
      Verified `1. 40 x 10 - feeling good` and `2. 60 x feel` still parse identically; all 22
      existing `tests/test_parse.py` tests pass unchanged.
- [x] Promoted `_parse_working_set_line`, `_parse_warmup_set_line`, `_parse_failure`,
      `_parse_quality` to module-level functions in `parser/parse.py`; the class methods are
      now one-line delegates. `tests/test_parse.py` needed no edits.
- [x] New `src/traininglogs/agent/exercise_block.py`:
      `ParsedBlock(warmup_sets, sets, exercise_rpe)` and
      `parse_exercise_block(chunk: str) -> ParsedBlock | None`. Splits on `Warmup:` /
      `Sets:` / `Remarks:`, routes non-blank lines to the matching line parser, reads
      exercise-level RPE from remarks (`RPE: 6-7` → `7.0`, upper bound). A block with no
      `Sets:` header, or no parseable working sets, or any line that fails to parse under
      `Warmup:`/`Sets:`, returns `None` — all-or-nothing, no partial result.
- [x] New `tests/test_agent_exercise_block.py`: all 6 blocks of
      `programmed_push_pull_session_with_remarks.md` (including that Chest Supported Rows has
      no exercise-level RPE at all in the real fixture — a genuine absence, asserted as
      `None`, not a bug), the empty-`Warmup:` Lateral Raise case, and two irregular-notation
      blocks (`18s - tuck, clean`; `5 attempts, 2 clean - band-assisted`) asserting `None`.
      8/8 pass. Full suite: 380 passed, 0 failed, 0 skipped.

### - [x] Step 2 — Branch the worker call in `assemble()` (`fix/extraction-accuracy-parse-first`) — done

Insertion point: `extraction.py` worker loop, *before* the existing `extract_exercise()` call —
this replaces that unconditional call with a branch, not a post-hoc reconciliation step.

| Field | Source, parsed path | Source, fallback path (parse failed) |
|---|---|---|
| `sets[].number`, `weight_kg`, `rep_count` | parser, directly | LLM (`ExerciseExtract`, unchanged) |
| `sets[].rpe` | LLM, assigned onto parser's index list (still a judgment call) | LLM |
| `sets[].notes` | LLM, keyed by parser's indices; unmatched keys dropped with a warning | LLM |
| `warmup_sets` | parser, directly | LLM |
| `name`, `tags`, `modality`, `movement_pattern`, exercise `notes`, `form_cues`, `target_muscle_groups`, `rep_tempo`, `current_goal` | LLM (`ExerciseLabelsExtract`) | LLM (`ExerciseExtract`) |

- [x] New `ExerciseLabelsExtract` schema (`schemas.py`) — no `sets`/`warmup_sets` fields;
      `set_notes: Dict[str, str]` keyed by set number as a string, plus
      `exercise_rpe_target_set: Optional[int]` for RPE placement.
- [x] New `LABELS_SYSTEM_PROMPT` (`prompts.py`) — small; no numeric-shape rules, since this
      path never touches sets/weights/reps at all.
- [x] New `extract_exercise_labels(text, position, set_numbers, provider)` in `extraction.py`,
      alongside the existing (unchanged) `extract_exercise()`. Unit tests in
      `tests/test_agent_exercise_labels.py` (5/5 pass), mirroring `TestExtractExercise`'s
      pattern in `tests/test_agent_extraction.py`.
- [x] `assemble()`: calls `parse_exercise_block(chunk_text)` before choosing which worker path
      to use (only when a chunk was isolated — never on the full-text fallback). New
      `_build_parsed_exercise()` + `_place_exercise_rpe()` helpers construct the final
      `Exercise` from parser output (numeric spine, unconditional) + `ExerciseLabelsExtract`
      output (everything else). A `set_notes` key that isn't among the parser's own set numbers
      is dropped with a warning, not treated as fatal. RPE placement defaults to the last set
      (matching the full-extraction path's own convention) unless the LLM names a different
      valid set number; if every candidate set already has its own inline RPE (parsed directly
      off a "RPE n" token on the set's own line), the value is left unplaced with a warning
      instead of silently dropped.
- [ ] `audit()`: the enumerated-line-count check was **not** added — see note below.
- [x] Updated `tests/test_agent_assembler.py` scripted payloads and dispatch (breakage note 1,
      as anticipated): `ScriptedProvider` now dispatches `LABELS_TOOL_NAME` too; new
      `_labels_raw()` fixture helper for the parsed path, `_exercise_raw()` kept only for the
      anchor-not-found fallback case. `TestAssembleSixExerciseRegression` simplified — since
      all 6 of the real fixture's exercises parse cleanly, it no longer hand-constructs
      weights/RPE at all; the parser reads them straight from the real fixture text.
- [x] New `TestAssembleReproducesOriginalFailures` in `tests/test_agent_assembler.py`: three
      end-to-end regression tests, one per original failure, each scripted with a labels
      response that omits exactly the information the original bad LLM call got wrong — proving
      each failure is now structurally impossible (weight/warmup: no field exists to drop them
      from; sets-vs-warmup_sets: no LLM decision about which field at all) or reduced to a
      code-level default rather than LLM judgment (RPE placement: defaults to last set when the
      LLM doesn't name one). 11/11 pass in `test_agent_assembler.py`; full suite 483 passed, 0
      failed, 0 skipped.

**Note — `audit()` line-count check deferred, not forgotten:** on the parsed path this check
would be trivially true by construction (parser guarantees it), and on the fallback path
(irregular formats: timed holds, attempts notation) there usually isn't a clean 1:1
line-to-set mapping to check in the first place — most of those formats collapse multiple
enumerated lines into one set (MyoReps, DropSet) or vice versa. Adding it now would mean
writing a check that's either always-true or frequently a false positive. Left out rather than
added speculatively; revisit if a real fallback-path miss is ever observed.

## Live-test findings after Step 2 (2026-08-02)

Ran `scripts/validate_with_model.py` against `openai/gpt-oss-120b` on the real 6-exercise
fixture. All three originally-targeted failures confirmed fixed (weight/warmup present on
Incline DB Press, RPE on Lat Pulldown's last set not the first, Lateral Raise's sets under
`sets` not `warmup_sets`). Three new, smaller issues surfaced — none are regressions of the
three original bugs, none are data corruption, and none require reopening Step 1 or 2:

1. **Duplicate RPE note.** Bench Press, Lat Pulldown, and Lateral Raise each show the correctly
   placed structured RPE on the last set (renders as `RPE 7`, no colon) *and* a redundant raw
   echo of the same remark in set 1's `notes` (renders as `RPE: 6-7`, with colon — confirmed
   these are different fields by reading `renderer.py`'s `_mark()`/format strings, not a
   misreading of the card). `LABELS_SYSTEM_PROMPT` never told the model not to restate a value
   it's already handling structurally via `exercise_rpe_target_set`.
2. **Spurious warmup note.** Lat Pulldown's card showed `Warmup note: 45kg x 5` — the model
   restated the warmup line's own already-parsed numbers instead of actual commentary.
3. **Shell-level focus truncation.** Session header showed `Powerlifting?` (real value:
   "Powerlifting and Mobility") — `SHELL_SYSTEM_PROMPT` literally instructs "use the short
   label, not a long description," and the model over-applied that to a value that wasn't
   descriptive filler. `TrainingMarkdownParser._parse_metadata_line()` (`parser/extract.py`)
   already parses `- Focus: ...` lines verbatim, no LLM, already used by the rules path — same
   "reach for deterministic parsing" principle as Steps 1/2, just applied to the shell call
   instead of the exercise call this time.

Checked which shell fields are actually free reuse before proposing Step 4 below: `date`,
`program`, `focus`, `week`, and `is_deload_week` are — `TrainingMarkdownParser`'s generic
`Key: Value` line parser and `DeepTrainingParser`'s yes/true/1 boolean logic already handle
them exactly, zero new code. `phase` (word ordinal → int, e.g. "One - Volume/Base Building" →
1) and `session_duration_minutes` (hrs+min string → total minutes, e.g. "1hrs 41min" → 101) are
**not** — confirmed by grep that no such converter exists anywhere in the codebase today, only
as prose instructions to the LLM. Those two need small new (tested) functions, not just reuse —
a materially different risk/effort category than the rest of this plan so far.

### - [ ] Step 3 — Labels prompt hygiene (not started)

Add two rules to `LABELS_SYSTEM_PROMPT` (`prompts.py`): (a) `set_notes` must never restate this
exercise's own weight/reps/RPE, including a whole-exercise RPE remark — that's handled via
`exercise_rpe_target_set`, not `set_notes`; only use `set_notes` for something ADDITIONAL about
that set (form, feel, a named correction); (b) `warmup_notes` must never restate the warmup
sets' own weight/rep numbers — only actual commentary about the warmup as a whole. Prompt-only
change, no schema/pipeline change. Proposed to Apoorva, not yet implemented — work paused
before starting it.

### - [ ] Step 4 — Shell parse-first (not started)

Mirrors Steps 1–2's pattern for `extract_shell()` instead of `extract_exercise()`. Deterministic
metadata parse (reusing `TrainingMarkdownParser`'s `Key: Value` line parser, already tested)
runs before the shell LLM call; if it finds `date`/`program`/`focus`/`week`/`is_deload_week`,
those come from the parse directly and the LLM's shell schema shrinks to `warmup`/`cooldown`/
top-level `notes` only. Two new small converters needed and not yet written: word-ordinal phase
("One" → 1) and hrs+min duration ("1hrs 41min" → 101) — each needs its own unit tests, same
diligence as `exercise_block.py`'s tests. All-or-nothing fallback to today's full
`extract_shell()` if the metadata block doesn't parse (e.g. genuinely freeform text with no
`- Key: Value` lines at all) — same safety property as Steps 1–2. Proposed to Apoorva, not yet
implemented — work paused before starting it.

### - [ ] Step 5 — Merge `fix/extraction-accuracy` → `dev`

- [ ] Full suite green, 0 skipped.
- [ ] `CHANGELOG.md` `[Unreleased]` entry.
- [ ] `docs/design.html` updated — the extraction pipeline now parses deterministically before
      calling the LLM on the common case, falling back to full LLM extraction only for
      irregular formats. This is a change in system shape.

## ▶ Resume here

**Work paused (2026-08-02) at Apoorva's request, mid-discussion of Steps 3 and 4 above —
neither has been started. No code was written for either; this section and the two step
write-ups above are the only new content from this discussion.**

**Correction (still relevant):** `fix/extraction-accuracy` had to be rebased off
`refactor/split-extraction-token-cost` instead of `dev` — see git log for the full note. This
means merging this plan's base branch to `dev` (Step 5) has to happen *after*
`refactor/split-extraction-token-cost` merges to `dev`, not before.

**Steps 1 and 2 done and squash-merged.** Suite green last verified at 483 passed, 0 failed, 0
skipped, before the uncommitted changes below existed.

**Uncommitted in the working tree right now — not mine, do not revert or assume ownership of
without checking with Apoorva:**
- `src/traininglogs/agent/providers.py` — `_NON_RETRYABLE_400_MARKERS` /
  `_is_retryable_bad_request()`: distinguishes a genuinely non-retryable 400 (billing/quota/
  permission) from a retryable schema-rejection 400, raising `LLMParserError` immediately for
  the former instead of burning the reask budget on a guaranteed failure.
- `src/traininglogs/agent/extraction.py` — `assemble()` gained a `use_parse_first` parameter
  and `DISABLE_PARSE_FIRST_ENV_VAR` env-var escape hatch, to run the pipeline with
  `parse_exercise_block()` disabled entirely (full LLM extraction for every exercise) for
  measurement/comparison purposes — explicitly documented in its own docstring as "not a
  production mode."
- `.gitignore` — new `eval_runs/` entry.
- New untracked: `scripts/eval_ab.py`, `scripts/eval_arms.py`, `arms_out.txt`, `eval_out.txt` —
  look like an A/B evaluation harness comparing parse-first on vs. off, run outputs included.
  Also still untracked and unrelated to this plan: `scripts/measure_prefix_tokens.py`,
  `scripts/spot_check_ai_parser.py`, `scripts/validate_with_model.py`.

**Next action:** confirm with Apoorva what to do with the uncommitted eval-harness work above
(commit as its own step, fold `use_parse_first` into this plan formally, or leave as a
standalone measurement branch), then resume Steps 3 and 4 as scoped above — Step 3 first
(small, no design question), Step 4 second (needs the two new converters + their tests,
test-first per `CLAUDE.md` phase order). Step 5 (merge to `dev`) stays blocked on
`refactor/split-extraction-token-cost` regardless.

---

## ✅ CLOSED 2026-08-02 — superseded by `roadmap.md`

This plan is closed. `roadmap.md` at the repo root is the forward plan. Nothing below was
abandoned silently; each open step has a recorded disposition.

**What closed it:** a measured model evaluation (`scripts/eval_arms.py`, artifacts in
`eval_runs/`, ~$0.58 total) established that **`parse_exercise_block()` fires on 0 of 10
exercises in real input files.** Its `_HEADERS = ("Warmup", "Sets", "Remarks")` requires
exact-match header lines; real logs use markdown (`### Working Sets`). The parse-first design
this plan delivered has therefore never run in production — it was validated only against the
older `tests/fixtures/valid/programmed_*.md` format.

The pure-AI pipeline scored 571/578 (98.8%) on 6 real sessions with Haiku 4.5, and 5 of the 7
misses were the model being *more* correct than the answer key (true accuracy ≈ 99.7%).
Decision: **remove parse-first from the AI path** rather than fix its header matching.

**Disposition of open steps:**

| Step | Disposition |
|---|---|
| **Step 3 — labels prompt hygiene** | **Re-targeted, not dropped.** Its two rules (`set_notes` must not restate this exercise's own weight/reps/RPE; `warmup_notes` must not restate the warmup sets' own numbers) were scoped against `LABELS_SYSTEM_PROMPT`, which is used only by `extract_exercise_labels()` — the parse-first path being deleted. The bugs are real and one was re-observed on 2026-08-02. The same two rules move to `WORKER_SYSTEM_PROMPT`, the surviving path. → `roadmap.md` Phase 1. |
| **Step 4 — shell parse-first** | **Rejected by decision, bug preserved.** Deterministic metadata parsing before the shell LLM call is hardcoded parsing in the AI pipeline, which Apoorva ruled out ("no parser hardcoding, we want ai native"). The bug that motivated it is real and still open: `focus` returned `"Powerlifting?"` for a source value of `Powerlifting and Mobility`. Root cause is already diagnosed above — `SHELL_SYSTEM_PROMPT`'s "use the short label, not a long description" instruction over-applies. Fix it by correcting that instruction, not by adding a parser. The two converters this step would have needed (word-ordinal phase, hrs+min duration) are **not** being written. → `roadmap.md` Phase 1. |
| **Step 5 — merge to `dev`** | **Executed as Phase 0.** The chain turned out to be linear: `fix/extraction-accuracy` already contains every commit from `refactor/split-extraction`, `-wire-orchestrator`, and `-token-cost` (verified `git log fix/extraction-accuracy..<each>` = 0). One squash-merge lands all of it, which satisfies this plan's own constraint that `-token-cost` reach `dev` first. |

**Uncommitted eval-harness work resolved:** `scripts/eval_ab.py` and `scripts/eval_arms.py` are
committed as the pipeline's regression harness. The `use_parse_first` toggle is committed as a
measurement escape hatch and is removed in Phase 1 along with parse-first itself.
