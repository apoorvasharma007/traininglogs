"""Regenerate all historical session data through the AI ingest pipeline (capture ->
extract -> confirm), producing a fresh dataset to compare against the rules-parser
output already in output_training_logs_json/.

Unlike scripts/regen_historical.py (rules parser, fully automatic, no review), this
drives the same interactive confirm loop `traininglogs log --parser ai` uses -- a
human reviews and confirms each session's card -- run here file by file across the
whole historical corpus. That is a deliberate choice, not a limitation: the model's
own reading can differ from the old rules-parser JSON in ways worth a human's eyes
(recovered warmup prose, corrected unilateral reps), and this is the one-time pass
where checking that matters most.

Safety:
- Never targets prod or the test DB -- REGEN_DATABASE_URL must be set explicitly,
  same convention as scripts/regen_historical.py.
- Writes JSON to a version-stamped directory (output_training_logs_json_v{VERSION}/
  by default), never the live output_training_logs_json/.
- Resumable: progress is tracked in <output-dir>/.regen_progress.json, keyed by
  file path. Re-running the script skips files already confirmed, so a multi-day
  manual review session costs nothing extra to resume. A file that failed or was
  interrupted is retried from scratch (a fresh capture -- capture() is intentionally
  not deduplicated, so this is a harmless extra raw_inputs row, not a bug).
- --max-cost stops the run before starting the next file once cumulative spend
  (summed from AnthropicProvider.calls, the real per-call cost Phase 3 added)
  crosses the cap. It does not interrupt a file in progress.
- --dry-run lists the files that would be processed and prints a cost estimate
  without calling the API. The estimate is not a prediction of this exact run --
  see the note above _ESTIMATED_COST_PER_FILE.

Usage:
    REGEN_DATABASE_URL=<url> .venv/bin/python scripts/regen_historical_ai.py --dry-run
    REGEN_DATABASE_URL=<url> .venv/bin/python scripts/regen_historical_ai.py --max-cost 10
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

INPUT_DIR = PROJECT_ROOT / "inputs"

# Measured on the 6-file eval set (roadmap.md): a full run costs ~$0.45, or
# ~$0.075/file. Not a prediction -- those 6 files are the eval corpus, not this
# corpus, and per-file cost scales with exercise count (one worker call each). Shown
# on --dry-run as an order-of-magnitude check, not a budget.
_ESTIMATED_COST_PER_FILE = 0.075


def _progress_path(output_dir: Path) -> Path:
    return output_dir / ".regen_progress.json"


def _load_progress(output_dir: Path) -> dict:
    path = _progress_path(output_dir)
    return json.loads(path.read_text()) if path.exists() else {}


def _save_progress(output_dir: Path, progress: dict) -> None:
    _progress_path(output_dir).write_text(json.dumps(progress, indent=2))


def main() -> None:
    from traininglogs import __version__

    parser = argparse.ArgumentParser(
        description="Regenerate historical session data through the AI ingest pipeline."
    )
    parser.add_argument("--dry-run", action="store_true",
                         help="List files and an order-of-magnitude cost estimate; no API calls, no DB writes.")
    parser.add_argument("--max-cost", type=float, default=10.00,
                         help="Stop before the next file once cumulative real spend crosses this (default $10).")
    parser.add_argument("--limit", type=int, default=None,
                         help="Process at most N files -- for trying the script out before a full run.")
    parser.add_argument("--files", nargs="+", default=None,
                         help="Process only these specific files (paths relative to the repo root "
                              "or absolute), instead of every .md file under inputs/.")
    parser.add_argument("--output-dir", type=Path, default=None,
                         help="Defaults to output_training_logs_json_v{app version}/")
    args = parser.parse_args()

    output_dir = args.output_dir or (PROJECT_ROOT / f"output_training_logs_json_v{__version__}")

    if args.files:
        md_files = [Path(f) if Path(f).is_absolute() else PROJECT_ROOT / f for f in args.files]
        missing = [f for f in md_files if not f.is_file()]
        if missing:
            print("ERROR: file(s) not found:")
            for f in missing:
                print(f"  {f}")
            sys.exit(1)
    else:
        md_files = sorted(INPUT_DIR.rglob("*.md"))
    if args.limit:
        md_files = md_files[:args.limit]

    print(f"Found {len(md_files)} .md file(s) under {INPUT_DIR}")
    print(f"Output directory: {output_dir}")

    if args.dry_run:
        estimate = len(md_files) * _ESTIMATED_COST_PER_FILE
        print(f"\n[dry run] No API calls made, nothing written.")
        print(f"Order-of-magnitude estimate for {len(md_files)} files: ~${estimate:.2f}")
        print("(from the roadmap's measured $0.075/file average on the 6-file eval set --")
        print(" actual cost depends on exercise count per file; treat this as a sanity check,")
        print(" not a budget)")
        return

    regen_url = os.environ.get("REGEN_DATABASE_URL", "")
    if not regen_url:
        print("ERROR: REGEN_DATABASE_URL is not set.")
        print("Never point this at DATABASE_URL (prod) or TEST_DATABASE_URL.")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    progress = _load_progress(output_dir)

    from traininglogs.agent.llm_orchestrator import LLMOrchestrator
    from traininglogs.agent.providers import AnthropicProvider
    from traininglogs.agent.schemas import TrainingLogLLMExtract
    from traininglogs.db.db import apply_schema, get_connection
    from traininglogs.db.fetch import get_extraction
    from traininglogs.ingest.capture import capture
    from traininglogs.ingest.confirm import confirm
    from traininglogs.ingest.extract import extract
    from traininglogs.processor.processor import relative_source_file, write_session_json

    conn = get_connection(regen_url)
    apply_schema(conn)

    # One provider for the whole run -- its .calls accumulates across every file, so
    # summing it at any point is the true cumulative spend, not just the last file's.
    provider = AnthropicProvider()
    total_cost = 0.0
    confirmed = skipped = failed = 0

    for md_path in md_files:
        rel = str(md_path.relative_to(PROJECT_ROOT))

        if progress.get(rel, {}).get("status") == "confirmed":
            skipped += 1
            continue

        if total_cost >= args.max_cost:
            remaining = len(md_files) - confirmed - skipped
            print(f"\n--max-cost ${args.max_cost:.2f} reached (spent ${total_cost:.4f}).")
            print(f"Stopping before {rel}. {remaining} file(s) remain.")
            print("Re-run the same command to resume -- already-confirmed files are skipped.")
            break

        print(f"\n{'=' * 60}\n{rel}\n{'=' * 60}")
        try:
            md_text = md_path.read_text(encoding="utf-8")
            source_file = relative_source_file(md_path)
            raw_input_id = capture(conn, md_text, source_kind="markdown", source_file=source_file)
            extraction_id = extract(conn, raw_input_id, provider=provider, model=provider.model)

            stored = get_extraction(conn, extraction_id)
            pending_extract = TrainingLogLLMExtract.model_validate(stored["extract"])

            orchestrator = LLMOrchestrator(correction_provider=provider)
            final_extract = orchestrator.confirm_loop(pending_extract)

            session = confirm(
                conn, extraction_id, final_extract, md_path=md_path,
                corrections=orchestrator.corrections, source_file=source_file,
            )
            write_session_json(session, output_dir)

            progress[rel] = {"status": "confirmed", "session_id": session.session_id}
            confirmed += 1
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            progress[rel] = {"status": "failed", "error": str(e)}
            failed += 1

        total_cost = sum(c["cost_usd"] for c in provider.calls)
        _save_progress(output_dir, progress)

    conn.close()

    print(f"\n{'=' * 60}")
    print(f"Confirmed: {confirmed}   Skipped (already done): {skipped}   Failed: {failed}")
    print(f"Total spend this run: ${total_cost:.4f}")
    print(f"{'=' * 60}")

    if failed:
        print("\nReview failures in .regen_progress.json before sign-off.")
        sys.exit(1)


if __name__ == "__main__":
    main()
