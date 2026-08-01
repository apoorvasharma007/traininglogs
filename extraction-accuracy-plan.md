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

### - [ ] Step 2 — Branch the worker call in `assemble()` (`fix/extraction-accuracy-parse-first`)

Insertion point: `extraction.py` worker loop, *before* the existing `extract_exercise()` call —
this replaces that unconditional call with a branch, not a post-hoc reconciliation step.

| Field | Source, parsed path | Source, fallback path (parse failed) |
|---|---|---|
| `sets[].number`, `weight_kg`, `rep_count` | parser, directly | LLM (`ExerciseExtract`, unchanged) |
| `sets[].rpe` | LLM, assigned onto parser's index list (still a judgment call) | LLM |
| `sets[].notes` | LLM, keyed by parser's indices; unmatched keys dropped with a warning | LLM |
| `warmup_sets` | parser, directly | LLM |
| `name`, `tags`, `modality`, `movement_pattern`, exercise `notes`, `form_cues`, `target_muscle_groups`, `rep_tempo`, `current_goal` | LLM (`ExerciseLabelsExtract`) | LLM (`ExerciseExtract`) |

- [ ] New `ExerciseLabelsExtract` schema (`schemas.py`) — no `sets`/`warmup_sets` fields;
      `set_notes: dict[int, str]` (or equivalent) for per-index notes.
- [ ] New `LABELS_SYSTEM_PROMPT` (`prompts.py`) — small; no numeric-shape rules, since this
      path never touches sets/weights/reps at all.
- [ ] New `extract_exercise_labels(text, position, set_indices, provider)` in `extraction.py`,
      alongside the existing (unchanged) `extract_exercise()`.
- [ ] `assemble()`: call `parse_exercise_block(chunk_text)` before choosing which worker
      function to call; construct the final `Exercise` from parser output (numeric spine) +
      LLM output (everything else), or from `ExerciseExtract` alone on the fallback path.
- [ ] `audit()`: add the enumerated-line-count check described above.
- [ ] Update `tests/test_agent_assembler.py` scripted payloads and dispatch (see breakage note 1).
- [ ] Regression tests reproducing all three original failures end-to-end with a fake provider,
      asserting: Incline DB Press keeps its weight/warmup (parser-owned, can't be dropped by the
      LLM), Lateral Raise's sets land in `sets` not `warmup_sets` (parser-owned, can't be
      misfiled), Lat Pulldown's RPE placement is exercised against a known index list (reduced
      risk, explicitly not asserted as guaranteed-correct).

### - [ ] Step 3 — Merge `fix/extraction-accuracy` → `dev`

- [ ] Full suite green, 0 skipped.
- [ ] `CHANGELOG.md` `[Unreleased]` entry.
- [ ] `docs/design.html` updated — the extraction pipeline now parses deterministically before
      calling the LLM on the common case, falling back to full LLM extraction only for
      irregular formats. This is a change in system shape.

## ▶ Resume here

**Step 1 done.** Squash-merged into base branch `fix/extraction-accuracy` as commit `f063ef3`.
Suite green: 380 passed, 0 failed, 0 skipped. Base branch not yet merged to `dev` — merges
only after Step 2 (and Step 3, the actual merge step) are also done.

Current branch: `fix/extraction-accuracy`. Working tree still has three untracked scripts
(`scripts/measure_prefix_tokens.py`, `scripts/spot_check_ai_parser.py`,
`scripts/validate_with_model.py`) unrelated to this plan — untouched.

**Next action:** cut `fix/extraction-accuracy-parse-first` from `fix/extraction-accuracy`, and
implement Step 2 — the `ExerciseLabelsExtract` schema, `LABELS_SYSTEM_PROMPT`,
`extract_exercise_labels()`, and the branch inside `assemble()`'s worker loop that calls
`parse_exercise_block()` before deciding which worker function to call. Tests first per
`CLAUDE.md` phase order.
