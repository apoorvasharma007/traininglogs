# Historical session review

## Goal

The 121 historical sessions (`bodybuilding_transformation_system`, Oct 2025 – Apr 2026) were
loaded into prod by the rules parser, which missed whatever didn't match its exact line formats:
warmups under `### Warm Up` / `### Warmup Sets` headings, `RPE` and quality after a stray word
(`60 kg x 6 reps RPE 8 Good`), warmups written as prose, and so on. Apoorva asked for a by-hand
review (Claude reading each source file against its prod rows) instead of a paid AI regeneration,
with every change logged here so it can be double-checked later.

## Rules

- Fix only what the source file says. Never infer, never tidy up wording.
- Anything ambiguous is logged as a **question** and left unchanged.
- The 9 app-logged Starting Strength sessions are out of scope (confirmed by Apoorva in the app).
- `session_id`s don't change.
- Changes go to prod one batch at a time, each batch one transaction, counts checked after.
- Every applied change is in `log.md` as before → after, with the source line it came from.

## Blast radius

- Prod tables `sessions`, `exercises`, `working_sets`, `warmup_sets` — historical rows only.
- `output_training_logs_json/bodybuilding_transformation_system/` — kept in sync with prod at the
  end (it is also `eval_arms.py`'s answer key). The uppercase
  `BODYBUILDING TRANSFORMATION SYSTEM/` copy is an older, wrong generation; left alone, flagged
  for Apoorva to decide.
- Backup before any change: `backups/prod-before-historical-review-2026-10-03.json` (gitignored).

## Tools

- `historical-review/check.py` — forgiving re-parse of every source file vs prod; lists every
  disagreement. Read-only.
- `historical-review/show.py <session_id>` — one session's source next to its prod rows.

## Steps

- [x] 0. Backup prod session tables (130 / 1048 / 2569 / 693).
- [x] 1. Run `check.py` over all 121 sessions; classify every finding. 341 findings: 77 sets with missing quality/RPE/note, 19 exercises with lost warmups (non-standard headings), 245 prose paragraphs with numbers.
- [x] 2. Batch 1 applied 2026-10-03 (`batch1.md`): 77 working sets filled (quality, RPE, notes — only where prod was empty; 0 conflicts), 24 warmup sets added. Counts 130/1048/2569/693 → 130/1048/2569/717. Re-check: 0 structured findings left.
- [ ] 3. Remaining batches applied.
- [ ] 4. Re-run `check.py`: only logged questions and accepted false alarms remain.
- [ ] 5. Regenerate the lowercase JSON copy for changed sessions; verify against prod.

## ▶ Resume here

**Waiting on Apoorva's approval of the prose plan (batch 2).** Proposed: convert warmups written as
prose into warmup sets **only where the exercise has no structured warmups** (~35 exercises:
Leg Press "Pyramid. 200 kgs power kicks", Leg Extension "36/43/50 x feel", Pec Dec "55 x 9", Seated
DB Shoulder Press "0 x feel / 2.5 x feel", Bulgarian Split Squat and Walking Lunge lists typed
under Notes). Leave prose where structured warmups already exist (the Incline DB Press routine
paragraph repeated in 23 sessions; calf raise duplicates) and goals/commentary. Log as questions:
"4.5 x feel… If needed" (instruction?), Seated DB Shoulder Press "17.5 x 13 RPE 8.5" under Warmup
Notes (working sets in the wrong section?). Prose text stays in notes either way.

Then step 5 (resync `output_training_logs_json/bodybuilding_transformation_system/`).

Branch `chore/historical-review` (from `dev`). Backup: `backups/prod-before-historical-review-2026-10-03.json`.
Release PR #32 (v3.1.0) is open, blocked on a required review: Apoorva merges it, or OKs `--admin`.
