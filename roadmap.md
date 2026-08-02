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

- [ ] Resolve the working tree — commit the eval harness + toggle + retry fix; delete dead
      `scripts/spot_check_ai_parser.py` (imports `agent.llm_parser`, removed); do not commit
      `eval_out.txt` / `arms_out.txt`. Two plan files carry pre-existing uncommitted edits from
      an earlier session — review before committing, do not clobber.
- [ ] Full suite green (`docker compose up -d` first).
- [ ] Squash-merge `fix/extraction-accuracy` → `dev`.
- [ ] Delete the three ancestor branches + the two squash-merged sub-branches.
- [ ] Delete stale feature branches (list generated and confirmed before deletion — destructive).
- [ ] Mark `orchestration-refactor-plan.md`, `extraction-accuracy-plan.md`,
      `movement-skill-plan.md`, `refactor-data-model.md` as superseded/complete.

## Phase 1 — Finalize the pipeline

Three of these are inherited open steps from the two closed plans — noted so their provenance
isn't lost.

- [ ] Delete `parse_exercise_block` and the parse-first branch from `assemble()`; remove
      `use_parse_first` and `DISABLE_PARSE_FIRST_ENV_VAR`. Also removes `extract_exercise_labels()`,
      `LABELS_SYSTEM_PROMPT`, and `ExerciseLabelsExtract`, which have no other caller.
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

**Nothing from Phase 0 has been executed.** The working tree is dirty (eval harness, parse-first
toggle, retry fix, two plan files with pre-existing edits). Branch deletion is destructive and
has not been done — the exact list must be generated and confirmed in-session before any
deletion.

**Next action:** Phase 0, step 1 — resolve the working tree and get the suite green.
