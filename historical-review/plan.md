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
- [x] 3. Batch 2 applied 2026-10-03 (`batch2.md`), approved by Apoorva: 64 warmup sets from prose, only on exercises with no warmup rows (39 exercises); 2 working sets for the 2025-10-25 Seated DB Shoulder Press, typed under Warmup Notes. Not converted by decision: goals, and "4.5 x feel … If needed" (an instruction). Counts → 130/1048/2571/781.
- [x] 4. Re-run `check.py`: 0 value differences. Remaining findings are accounted for: 40 count differences that are exactly batch 2's additions (the checker reads only structured lists), and prose paragraphs judged as goals/commentary or as routine text on exercises that already had warmups.
- [x] 5. `sync_json.py`: 168 values filled across 66 files in `output_training_logs_json/bodybuilding_transformation_system/`, each validated as a `TrainingSession`; a rerun finds nothing. The uppercase copy is untouched.

## ▶ Resume here

**Done.** Prod went from 2569 working sets / 693 warmup sets to 2571 / 781, plus 77 working sets
with restored quality, RPE or notes; the JSON copy matches. To undo any of it, restore from
`backups/prod-before-historical-review-2026-10-03.json` (local only). Open, for Apoorva: delete
the older uppercase `output_training_logs_json/BODYBUILDING TRANSFORMATION SYSTEM/` copy, which
`eval_arms.py` still reads alongside the correct one.
