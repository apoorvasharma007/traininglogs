# scripts/

Three scripts, run from the repo root with `.venv/bin/python scripts/<name>.py`. Each one's
docstring has the full usage. Anything else gets written when it's needed.

| Script | What it does | Costs money |
|---|---|---|
| `correction_stats.py` | Reads the corrections log of confirmed sessions and prints which fields get corrected most, by source (tapped on the card or typed), and how many sets and exercises the model missed. Read-only. | No |
| `eval_arms.py` | Scores the AI extraction against an answer key (`output_training_logs_json/`): set counts, weights, reps, RPE, warmups. Run it before and after a prompt change to see whether accuracy moved. | Yes |
| `eval_ab.py` | Compares models (Haiku and Groq) on the same sessions. `eval_arms.py` also imports its response cache and cost tracking, so it stays even when you don't use it directly. | Yes, for Haiku |

Both eval scripts cache every model response on disk in `eval_runs/.cache/`, so a re-run never
pays twice for the same call. Before any paid run:

1. Run it with `--dry-run`. It lists every call it would make, which ones are already cached,
   and spends nothing.
2. Run it for real with `--max-cost`, which stops before the next call once spending passes the
   cap.

A prompt or schema change changes the cache key, so the next run pays again. Batch prompt
changes into one measurement instead of measuring each one.
