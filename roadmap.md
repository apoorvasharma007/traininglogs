# traininglogs roadmap — from local script to hosted app

Supersedes `orchestration-refactor-plan.md`, `extraction-accuracy-plan.md`, and the Cloud
Deployment Wave in `pre-online-plan.md`. Those stay in the repo as the historical record of how
their decisions were reached; this file is the forward plan.

---

## Goal

> Finish a workout. Paste notes, photograph the notebook, or talk into the phone. Seconds later
> a card shows what the system understood, with anything uncertain flagged. Glance, fix a number
> if needed, tap confirm. It's in the log — queryable, on the dashboard, forever. The raw input
> is never thrown away.

Today the app is a local CLI that does git commits and rebuilds a static dashboard as part of
ingestion. The gap between those two sentences is this roadmap.

---

## Architecture decisions — locked, with evidence

Settled by the model evaluation on 2026-08-02 (`scripts/eval_arms.py`, artifacts in
`eval_runs/`). Do not relitigate these without new measurements.

| Decision | Evidence |
|---|---|
| **Model: Claude Haiku 4.5.** Not Groq. | Haiku 4/4 exact on set counts across the fixture set; `openai/gpt-oss-120b` 1/4, dropping 4 and 3 sets on two files with **zero** warnings raised. |
| **Pipeline is AI-native. No deterministic parser in the extraction path.** | `split-nopf` scored 571/578 (98.8%) on 6 real sessions; 5 of the 7 misses were the model being *more* correct than the answer key. True accuracy ≈ 99.7%. |
| **`parse_exercise_block` is deleted, not fixed.** | It fires on **0 of 10** exercises in real input. `_HEADERS = ("Warmup", "Sets", "Remarks")` requires exact-match headers; real logs use `### Working Sets`. It has never run in production. |
| **Keep the split-call architecture.** | Accuracy vs monolithic is a tie (339 vs 337 fields). But monolithic output is 3.6–4.1K tokens and hit the `max_tokens=4096` ceiling on 2 of 6 files, producing truncated JSON. Split keeps each call at 400–800 tokens — permanent headroom that grows with session size. |
| **Warmup-Notes prose is structured data.** | Users write warmups as prose under `### Warmup Notes` with `### Warmup` empty (`36 x feel`, `200 kgs power kicks`). The rules parser dropped all of it — the historical DB is missing this data. The model recovers it correctly. |

**Known open defect:** the model reads asymmetry commentary as unilateral rep counts.
`12.5 x 13 - right did partial range only` became `unilateral_rep_count={right:{full:13}}` with
`rep_count=None`. Schema-valid, plausible, wrong — and undetectable by token-presence checks,
because `13` is still in the output. Fixture: `Wrist Flexion DB Curl` in
`inputs/programs/bodybuilding_transformation_system/phase_2/week_12/upper_strength_foundation_block.md`.

---

## Conventions

**Read `extraction-design-principles.md` before changing a prompt or a schema.** It records what
production extraction teams and published research actually find works — including several
findings that contradicted our own assumptions. The short version: the schema is a bigger lever
than the prompt, flat beats nested, field names are search hints, and 2-4 real examples beat more.

**Spend as little on the API as possible.** The cache key is a hash of the whole request --
model + system prompt + tool schema + input text -- so:

| Change | Cost to verify |
|---|---|
| Python only (checks, parsing, glue) | **$0.00** — every call replays from `eval_runs/.cache/` |
| Prompt or schema | **~$0.45** for a 6-file run — every worker call is a fresh hash |

So: **batch prompt and schema changes, then measure once.** Measuring after each of B6/B7/B8
separately costs ~$1.35; doing all three then measuring costs ~$0.45, for the same information.
Always `--dry-run` first to see what is already cached, and always pass `--max-cost`.

Spend so far: **$1.21** across 158 paid calls (158 cached, none paid for twice).


**Name things in plain words.** No `provenance`, no `cardinality`, no `coverage`. A function name
should say what it checks in words you'd use out loud: `check_sources_are_real()`,
`check_sets_and_sources_match()`, `check_for_unread_lines()`. This applies to new code; existing
names are left alone unless they're actively confusing.

**Watch the size.** The codebase is large for what it does. Every addition should remove a
category of bug, not just add capability — parse-first removal was −740 lines, and patch-based
corrections (C6) will remove more than they add. If an item is pure growth, say so out loud
before building it.

## Settled during planning (2026-08-03)

| | Decision |
|---|---|
| Rules parser | **Kept** as a backup pipeline. Not deleted. |
| `output_training_logs_json/` | **Existing 242 files kept and never modified** — they are the eval answer key. Stop *writing* new ones once layer 3 is in Postgres (a third copy of data that lives in two places). |
| The unilateral defect | **Accepted.** `12.5 x 13 - right did partial range only` → `unilateral_rep_count={right:{full:13}}` is not generically detectable; the confirmation card is the guard. |
| `mono` at `max_tokens=8192` | **Re-run** (~$0.06) so the split-vs-mono verdict rests on an unconfounded result rather than an inference. |
| `max_tokens=4096` | **Make configurable** in `providers.py`. Fine for split calls, fatal for monolithic. |
| Eval-set expansion | **After deploy.** The 6 real files have free ground truth; the irregular `adhoc_*` cases need hand-labels. |
| Anthropic Citations | **Check before building B1** — may do source grounding natively, but may not compose with tool use. |
| `movement-skill-plan.md`, `refactor-data-model.md` | **Close** — both complete. |

## Working backwards from the goal

| | For the goal to be true… | Needs | Phase |
|---|---|---|---|
| A | extraction is accurate and AI-native | split pipeline, no hardcoded parser | ✅ done |
| B | a bad parse is a re-run, not a code fix | `raw_inputs` + `extractions` tables | 2 |
| C | input can come from a phone | identity decoupled from file paths | 2 |
| D | ingestion can run server-side | ingest core with no `input()`/`git`/dashboard | 3 |
| E | a client can drive it | write endpoints | 4 |
| F | usable from a phone | web confirm UI | 5 |
| G | not on my laptop | API deployed (Supabase already live) | 6 |

---

## Phase 0 — Land what's in flight

The chain `refactor/split-extraction → …-wire-orchestrator → …-token-cost →
fix/extraction-accuracy` is **linear**: the tip contains every commit from all three ancestors
(verified `git log fix/extraction-accuracy..<each>` = 0). One merge lands all of it, and that
automatically satisfies `extraction-accuracy-plan.md`'s constraint that token-cost reach `dev`
first.

- [x] Resolve the working tree — three atomic commits (`5c3a496` retry fix, `b669251` eval
      harness, `58b12e2` plan closures + roadmap). `spot_check_ai_parser.py` (dead import) and
      `validate_with_model.py` (Groq-specific, superseded) retired to scratchpad rather than
      deleted. `eval_out.txt` / `arms_out.txt` gitignored.
- [x] Full suite green — **483 passed, 0 failed, 0 skipped**, matching the pre-work baseline.
- [x] Merge `fix/extraction-accuracy` → `dev` (`9bde4f6`). Used `--no-ff` rather than squash:
      the chain was 29 commits of real staged work and a fast-forward would have hidden the
      phase boundary. Suite re-verified green on `dev` after the merge.
- [x] Delete the three ancestor branches — done with `git branch -d` (not `-D`), so git itself
      verified containment.
- [ ] Delete the remaining 12 stale branches — **deferred until `dev` reaches `main`**, when
      `-d` can clear the genuinely-merged ones without a judgement call. Branch counts are
      misleading for squash-merged branches (`feature/ai-parser-terminal-renderer` shows 1
      "unique" commit but `agent/renderer.py` is in the tree). Clutter is cheap; deleted work
      is not.
- [x] `orchestration-refactor-plan.md` and `extraction-accuracy-plan.md` closed with a recorded
      disposition for every open step.
- [ ] Mark `movement-skill-plan.md` and `refactor-data-model.md` complete (both appear done;
      confirm before closing).

## Phase 1 — Finalize the pipeline

Three of these are inherited open steps from the two closed plans — noted so their provenance
isn't lost.

- [x] **Delete parse-first** (`3afafb2`). Removed `parse_exercise_block` + `exercise_block.py`,
      `extract_exercise_labels`, `LABELS_SYSTEM_PROMPT`, `ExerciseLabelsExtract`,
      `_place_exercise_rpe`, `_build_parsed_exercise`, `use_parse_first` /
      `DISABLE_PARSE_FIRST_ENV_VAR`, and `eval_arms`' `split-pf` arm. −740 lines.
      Suite 467 green (was 483; the 16 removed covered deleted code).
      **Coverage tradeoff, recorded deliberately:** `TestAssembleReproducesOriginalFailures`
      proved two of the three original extraction failures were structurally impossible — a
      guarantee that held *because* the parser owned the numeric spine. With the model owning
      it, those tests would assert only that a scripted value came back unchanged, so they were
      deleted rather than rewritten into something weaker than they look. That coverage now
      lives in `scripts/eval_arms.py` (measured against real sessions) and in `audit()` — which
      makes the `audit()` rewrite below the item that restores the guard, not just a nice-to-have.
- [ ] **B1 — Source lines on the extraction.** `set_sources` / `warmup_sources` on
      `ExerciseExtract`: set number -> the verbatim line it was read from. Goes on the
      *extraction*, not on `WorkingSet` — `ExerciseExtract` inherits from the production
      `Exercise`, so a field there would mean a DB column, API change, and dashboard change.
      Same idea as the existing `ExercisePosition.anchor`, one level down.
- [ ] **B2 — `check_sources_are_real()`.** Every recorded source line must appear verbatim in
      the chunk. A line that doesn't resolve was invented. Zero false positives by construction.
- [ ] **B3 — `check_sets_and_sources_match()`.** Every set has a source; every source has a set.
      Catches phantom sets and dropped ones.
- [x] **B1–B3 done** (`ab2ed8d`, `9c8dbc4`). Measured on 6 real sessions, 102 sets:
      **0 false positives, 0 set/source mismatches, accuracy unchanged at 571/578 (98.8%)** --
      so adding the field did not degrade extraction. One correction along the way: exact string
      matching produced 4 false "may be invented" warnings, all from the model typing a plain
      character where the file had a typographic one (U+2019 curly apostrophe, U+00A0
      non-breaking space). `_comparable()` now compares content, not bytes. The claim that B2
      had "zero false positives by construction" was wrong -- real text has more variation than
      that.
      **Validated 2026-08-04 on live output, free:** run against `openai/gpt-oss-120b`, the
      checks fired 13 times on one real session -- Groq ignored the source-line instruction on
      2 of 3 exercises, producing sets with no sources at all. Haiku recorded a source for
      102/102 sets; Groq for 3/10. So the checks do fire on real model output, and they flag
      exactly what they should: an extraction that cannot show its work.
      **Still narrowly unproven:** the "source with no set" branch (a line read then dropped)
      has only ever fired in unit tests -- Haiku has not produced that shape. Not worth paying
      to manufacture; it will surface on its own or it won't matter. Groq's free-tier quota was
      exhausted after 5 calls, so a fuller Groq comparison is available later for $0 whenever
      the quota resets.
- [x] **B4 — REJECTED on measurement, 2026-08-04.** Counted what it would flag on one real
      session: 76 lines contain a number, only 36 are enumerated set entries. The other **40
      would all be false positives** — Date, Phase, Week, Duration, `## Exercise 1`,
      `**Name:** Incline DB Press 45 Degree`, `**Goal:**`, `**Rest:**`, warmup prose. Making it
      precise means teaching it that a set looks like `^\d+[.)]`, which is exactly the
      format-specific overfit this plan rules out — and that pattern dies on speech input.
      Not built. A set dropped together with its source line stays undetectable; that is an
      accepted limit, not an oversight.
- [x] **B5 — kg check removed, RPE check kept** (2026-08-04). Measured across all 122 input
      files: 1,009 of 1,036 kg-suffixed numbers are on `**Goal:**` lines, 27 are prose, and
      **none** are working-set weights (sets write `63 x 10`, no unit). It could only ever fire
      on goal weights, so all 9 of its warnings were noise and it could never catch a dropped
      weight. The RPE check stays — sets write `RPE 10` inline, and "RPE" is domain vocabulary
      that survives a change of input format.
      **Result: warnings across 6 real sessions went 13 -> 0**, accuracy unchanged at 571/578.

  Design principle for all of these: a check should encode a **property of the data**, not a
  **memory of a bug**. "Every number in the source should be accounted for" survives new input
  formats; "watch out for unilateral_rep_count on this shape of line" dies the moment the input
  changes. That rules out the unilateral rule proposed earlier — it is explicitly not being
  built. Warnings are *attention direction* for the confirmation card, not a safety net: a false
  warning costs two seconds of reading, a missed one costs wrong data.
### Reordered 2026-08-04 — schema before prompt

Research (`extraction-design-principles.md`) says we had the priority backwards: 55% of accuracy
improvements come from flattening schemas, and one field rename moved a benchmark from 4.5% to
95%. We were about to spend on prompt wording while the schema stayed 6 levels deep with two
competing fields for "reps". The prompt items below are still wanted; they now come *after* the
schema work, and against a much smaller schema.

**Test each change on Groq first — it is free.** If schema complexity is the real constraint, the
weaker model improves most, and we learn the direction for $0.00 before spending on Haiku.
See the open hypothesis at the end of `extraction-design-principles.md`.

- [ ] **S1 — Split the extraction schema from the database model.** `ExerciseExtract` currently
      inherits from `Exercise`, the production model behind the `exercises`/`working_sets` tables,
      so the model is asked to fill a shape designed for storage. Make it standalone, carrying
      only the fields the POC needs, and add a projection function to `Exercise`. **No DB, API or
      dashboard change** — the projection absorbs it. Needs a decision on the POC field set.
- [ ] **S2 — Flatten `reps` to one field.** `rep_count` (2 levels) and `unilateral_rep_count`
      (4 levels) are two competing fields for one concept; the model must infer which applies,
      which is the Wrist Flexion defect. Replace with a single string field the model copies from
      the text (`"8"`, `"8+1"`, `"L8/R7"`, `"12 catches"`), parsed deterministically in Python.
      Grounding already proves the copy is faithful.
- [ ] **S3 — Field names and descriptions.** Name fields the way the source names them; give every
      field an explicit scope description in the schema rather than a rule in the prompt.
      (Findings 1 and 4: 4.5%→95% on a rename; 34% of improvements from descriptions.)
- [ ] **S4 — Add 2-4 few-shot examples** drawn from real inputs covering the notation variety
      (barbell sets, timed holds, unilateral, "x feel" warmups). Currently there are **zero**.
      (Finding 6: up to +17%.)
- [ ] **Worker prompt hygiene** *(inherited: extraction-accuracy Step 3, re-targeted from
      `LABELS_SYSTEM_PROMPT` to `WORKER_SYSTEM_PROMPT`)*. Two rules: `set_notes` must never
      restate this exercise's own weight/reps/RPE — only something additional about that set
      (form, feel, a named correction); `warmup_notes` must never restate the warmup sets' own
      numbers — only commentary about the warmup as a whole. Prompt-only, no schema change.
- [ ] **Shell focus truncation fix** *(inherited: extraction-accuracy Step 4, approach rejected,
      bug preserved)*. `SHELL_SYSTEM_PROMPT`'s "use the short label, not a long description"
      over-applies — `Powerlifting and Mobility` came back as `Powerlifting?`. Fix the
      instruction. Do **not** add a deterministic metadata parser; that was the rejected
      approach, and the word-ordinal-phase and hrs+min-duration converters it needed are not
      being written.
- [ ] Encode the Warmup-Notes convention in `prompts.py`.
- [ ] **Prompt caching** *(inherited: orchestration Step 8.5 — was blocked on a dead API key,
      now live)*. Enable on `AnthropicProvider` with `cache_read_input_tokens` measured
      before/after. The splitter (~670 tok) and shell (~1,400 tok) prefixes are **below Haiku
      4.5's 4,096-token minimum** and will silently not cache — only the ~5,400-token worker
      prefix will. `scripts/measure_prefix_tokens.py` confirms this against the real endpoint.
- [ ] Promote `scripts/eval_arms.py` + the 6-file sample to a repeatable regression check.

## Phase 2 — Three layers

- [ ] `raw_inputs` table: id, content, `source_kind` (`markdown`|`photo`|`speech`), captured_at,
      checksum. Immutable.
- [ ] `extractions` table: id, `raw_input_id` FK, model, prompt_version, created_at, full
      extract as JSONB, `uncertain_fields`, `warnings`, status
      (`pending`|`confirmed`|`rejected`), confirmed_at.
- [ ] `sessions.extraction_id` FK.
- [ ] Re-key `session_id` off `raw_inputs.id`, not the file-path hash
      (`processor.compute_session_id`). Keep the date prefix for readability.
- [ ] Stop dropping the confidence signal — `build_session_from_extract` currently does
      `exclude={"uncertain_fields"}` and discards `warnings` entirely.
- [ ] **C6 — Patch-based corrections.** `LLMExtractValidator.apply_correction` currently sends
      the whole extract and asks for the whole extract back, with "keep all unchanged fields
      exactly as they are" as the only guarantee — a hope, not a mechanism. It also uses
      `SYSTEM_PROMPT`/`TOOL_NAME`, i.e. the monolithic path that hit `max_tokens=4096` and
      truncated on 2 of 6 files in the evaluation. Replace with a patch: the model returns
      `[{path, value}]`, Python applies it. ~40x cheaper (~$0.028 -> ~$0.0007 per correction),
      and fields not named in the patch cannot change *by construction*.
- [ ] **C7 — `corrections` JSONB, append-only; `extract` stays immutable.** Keeps three facts
      forever: what the model said, what the human changed, what was stored. Byproduct: "which
      fields do I correct most often?" becomes a SQL query — the prompt-improvement backlog,
      generated from real use.
- [ ] **C8 — LIVE BUG: `source_file` is never set on the AI path.** `process_md_file` sets it
      (rules path only, `processor.py:158-168`); `_process_with_ai` in `cli/log.py` never does.
      Every AI-parsed session currently in the DB has no link to the text it came from. Fixed
      properly by C1-C3 (the `raw_input_id` FK), but worth knowing it is broken today.
- [ ] **C9 — Decision, not code:** keep `set_sources` in the `extractions` row rather than
      discarding it after the audit. It is what lets the confirmation card show "3 sets @ 90kg"
      next to "read from: `1. 90kg x 8`", and eventually highlight a region of a photographed
      page. Costs nothing extra to keep.

## Phase 3 — Ingest core

Three durable states, three steps between them. Each step reads its input **from the database**,
not from the previous function's memory — that is what makes any of it restartable.

```
   capture()              extract()                  confirm()
text ────────▶ raw_inputs ──────────▶ extractions ───────────────▶ sessions
               (saved)      N LLM      (saved,          human       (saved)
                            calls      pending)         decides
```

- [ ] **D1 — `ingest/` module**: `capture.py` (text -> raw_input_id), `extract.py`
      (raw_input_id -> extraction_id), `confirm.py` (extraction_id -> session_id). One job each,
      each saves before returning.
- [ ] **D2 — `cli/` and `api/` both call `ingest/`; neither holds logic.** If logic is being
      copied between them, it belongs in `ingest/`.
- [ ] **D3 — `status` column is the state machine.** Gives idempotency for free: re-running
      extract on an input that already has one must not spend money producing a second copy.
- [ ] **D4 — `llm_calls` table**: raw_input_id, step, model, input/output tokens, cost_usd, ms,
      cached. Makes cost a SQL query. Already prototyped as `calls.jsonl` in the eval harness.
- [ ] **D5 — Structured logs carrying `raw_input_id`** on every line, so one id shows a
      session's whole life.
- [ ] **D6 — Save the raw LLM response before parsing it.** A validation failure should not also
      cost you the response.
- [ ] **D7 — Log "call succeeded" and "result usable" separately.** The `mono` truncation was the
      former, not an outage; conflating them misdiagnoses failures.
- [ ] **D8 — Strip `git`, dashboard rebuild, and `input()` out of the ingest path.** This, not
      the Dockerfile, is what blocks hosting: a blocking terminal prompt cannot sit behind an
      HTTP endpoint no matter where it is deployed. `cli/log.py` keeps its git/dashboard work as
      a thin wrapper around the core.

**Deliberately NOT built at this scale** (~20 sessions/month): no queue (Celery/SQS/Redis — the
status column is the queue), no microservices, no retry framework (the SDK retries), no provider
abstraction layer (one provider, one model), no caching before measuring. The point is that the
*shape* is queue-ready, not that a queue exists.

## Phase 4 — Write API

- [ ] `POST /inputs` → `{raw_input_id, extraction_id}`
- [ ] `GET /extractions/{id}` → validation-card JSON (reuse `ValidationCardBuilder`; swap
      `TerminalRenderer` for a JSON serializer)
- [ ] `POST /extractions/{id}/confirm` → writes the normalized session
- [ ] `POST /extractions/{id}/correct` → re-runs correction, returns updated card

## Phase 5 — Confirm UI

New surface in `traininglogs`. **v1 is deliberately minimal**: a textarea, a rendered card, a
confirm button. Mobile capture comes later.

## Phase 6 — Deploy

- [ ] Deploy FastAPI to Fly (`fly.toml` and `Dockerfile` already exist). Supabase is live with
      121 sessions (`pre-online-plan.md` Cloud Wave Step 1, done 2026-05-07).
- [ ] Env: `DATABASE_URL`, `API_KEY`, `ALLOWED_ORIGINS`.
- [ ] Smoke-test read + write paths.

## After end-to-end works

- [ ] **Historical regeneration** — recover the warmup data the rules parser dropped across
      ~121 sessions. Deferred by explicit decision until a working end-to-end version exists.
      Requires Phase 2 (re-runnable extraction). ~$5 at Haiku rates.
- [ ] Photo input — new `source_kind`, vision model. Not a new pipeline.
- [ ] Speech input — new `source_kind`, ASR → text → same pipeline.

---

## Branching

Base branch per phase, cut from `dev`. Sub-branch per step, squash-merged to the base. Base
merges to `dev` only when the phase is complete and the suite is green (0 failed, 0 skipped).

---## ▶ Resume here

**Architecture decisions locked** from the 2026-08-02 evaluation. **Full backlog approved**
2026-08-03. **Phase 1 reordered 2026-08-04** — schema before prompt, on evidence.

**Done:** Phase 0 (`dev` at `99c9fae`). Phase 1: parse-first deleted (`3afafb2`); source lines +
their two checks (`ab2ed8d`, `9c8dbc4`), validated live on Groq for $0; B4 rejected and B5
narrowed on measurement (`92f0073`). Suite **483 passed / 0 failed / 0 skipped**. Nothing pushed.

**Spend: $1.21 of $5.00.**

**In progress:** `phase-1/prompt-fixes`, cut from `phase-1/finalize-pipeline`. **Nothing committed
on it yet** — the branch holds only an untracked baseline capture in the scratchpad. The prompt
work was paused mid-flight when the research showed the ordering was wrong.

### Next action: S1 — split the extraction schema from the DB model

`ExerciseExtract(Exercise)` at `schemas.py:68` is the coupling. Breaking it is the prerequisite
for S2-S4 and costs nothing at the DB layer.

**Ask Apoorva first — this needs a decision, not a guess:**

1. **Which fields are in the POC extraction schema?** Proposed minimum: exercise `name`, `sets`
   (weight, reps, RPE, notes), `warmup_sets`, exercise `notes`. Proposed to drop *from extraction
   only*: `tags`, `modality`, `movement_pattern`, `rep_tempo`, `target_muscle_groups`,
   `current_goal`, `form_cues`. They stay in the DB model; they just stop being asked of the model
   for now. Fewer fields measurably improves accuracy on the rest (finding 3).
2. **What happens to the dropped fields in the DB** — left null, or backfilled later by a separate
   classification call?

### Measurement strategy for S1-S4 — Groq first, free

Each of S1-S4 changes the schema, so each invalidates the worker cache (~$0.45 on Haiku). To keep
the spend down:

1. Run the change on **Groq first** (`--model groq`, $0.00). If schema complexity is the real
   constraint, the weaker model improves most — that is the hypothesis being tested.
2. Only spend on Haiku once a batch is settled. Batch **S1+S2** (both schema shape) and **S3+S4**
   (both schema metadata and examples) — two Haiku measurements, ~$0.90, instead of four at ~$1.80.
3. Groq's free quota was exhausted on 2026-08-04 and resets on its own; check before planning a
   Groq run.

Baseline to beat: **571/578 (98.8%), 0 warnings, 3/6 files perfect.** A drop means revert, not
patch.

### Then, against the smaller schema

B6 (worker prompt hygiene), B7 (shell focus truncation), B8 (warmup-notes convention), then B9
(prompt caching) last. Detail for each is in the Phase 1 list above.

### Also found on 2026-08-04, not yet fixed

`WORKER_SYSTEM_PROMPT` carries a 497-character block of `program`/`phase`/`week` rules —
session-level fields `ExerciseExtract` does not have and the worker cannot extract. Roughly 125
wasted tokens on every worker call, ~8 calls per session, plus instruction about fields not in the
schema. `tests/test_agent_prompts.py::test_has_no_session_level_fields` was written to catch this
and its pattern missed (it guards `"program":`, the prompt says `"Program:"`). Fold the deletion
into S3 and tighten the test guard.
