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
- [ ] Rewrite `audit()`: per-exercise set-count check against enumerated source lines; flag
      `unilateral_rep_count` populated where the source line has no left/right marker. Keep the
      RPE/kg token checks. Tune for sensitivity — a false warning costs two seconds of reading,
      a missed one costs wrong data.
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

## Phase 3 — Ingest core

- [ ] Extract pure functions from `cli/log.py`: text → extraction id. No `input()`, no
      `subprocess`, no `git`, no dashboard rebuild.
- [ ] `cli/log.py` becomes a thin wrapper that calls the core, then does its git/dashboard work.
- [ ] `LLMOrchestrator`'s confirm loop moves out of the ingest path.

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

---

## ▶ Resume here

**Written 2026-08-02.** Architecture decisions locked above from the model evaluation run the
same day; total eval spend ~$0.58.

**Phase 0 complete.** `dev` is at `99c9fae` with the whole split-extraction +
extraction-accuracy chain landed. Three ancestor branches deleted (`-d`, verified contained).
Twelve stale branches deliberately left until `dev` → `main`. Nothing has been pushed.

**Phase 1 in progress** on `phase-1/finalize-pipeline` (cut from `dev`), sub-branch per item.
Item 1 (delete parse-first) done and squash-merged — `3afafb2`, suite **467 passed / 0 failed /
0 skipped**.

**Next action: rewrite `audit()`.** It moved up the order deliberately: deleting parse-first
removed the structural guarantee that two of the three original extraction failures couldn't
happen, so `audit()` is now the only runtime guard against them. Its known blind spots, each
with a real example from the 2026-08-02 evaluation:

1. **Per-exercise set count.** Groq dropped 4 sets on one fixture and 3 on another with
   `warn=0` — `audit()` compares *exercise* counts against the splitter, never set counts.
2. **Timed / bodyweight sets carry no kg tokens.** `20s`, `18s`, `15s` — the weight-token check
   has nothing to look for, leaving the whole calisthenics input class unguarded.
3. **Structural misplacement.** `12.5 x 13 - right did partial range only` became
   `unilateral_rep_count={right:{full:13}}` with `rep_count=None`. Both numbers are still in the
   output, so every token-presence check passes. Fixture: `Wrist Flexion DB Curl` in
   `inputs/programs/bodybuilding_transformation_system/phase_2/week_12/upper_strength_foundation_block.md`.

Then the two inherited prompt fixes, then caching last — caching is the only item whose
measurement depends on the final call structure.

Re-run `scripts/eval_arms.py --n 6 --arms split` after each item. Responses are cached, so a
re-score after a prompt change costs only the calls whose prefix actually changed.
