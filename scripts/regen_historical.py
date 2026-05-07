"""Regenerate all historical JSON files using the current processor pipeline.

Safety-isolated: writes to a fresh output directory, never overwrites the live
output_training_logs_json/. After reviewing output, swap directories manually.

Usage:
    REGEN_DATABASE_URL=<url> python scripts/regen_historical.py [--overwrite] [--output-dir DIR]

Requires a running isolated target DB — never point this at the prod or test DB.
See .claude/regen-historical.md for the full workflow and sign-off steps.

After a successful run, review the output then swap:
    mv output_training_logs_json output_training_logs_json_old
    mv <output-dir> output_training_logs_json
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.processor.processor import process_md_file

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output_training_logs_json_regen"
INPUT_DIR = PROJECT_ROOT / "inputs"


def main() -> None:
    regen_url = os.environ.get("REGEN_DATABASE_URL", "")
    if not regen_url:
        print("ERROR: REGEN_DATABASE_URL is not set.")
        print("Set it to the URL of an isolated target DB (not prod, not test).")
        print("Example: postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Regenerate historical JSON files.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Truncate the target DB before running (safe to re-run from scratch).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for regenerated JSON (default: {DEFAULT_OUTPUT_DIR}).",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = get_connection(regen_url)
    apply_schema(conn)

    if args.overwrite:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE sessions CASCADE")
        conn.commit()
        print("Truncated target DB (cascaded to all child tables).")

    md_files = sorted(INPUT_DIR.rglob("*.md"))
    if not md_files:
        print(f"No .md files found under {INPUT_DIR}")
        sys.exit(1)

    print(f"Found {len(md_files)} .md file(s) under {INPUT_DIR}\n")

    processed = 0
    skipped = 0
    failed = 0

    for md_path in md_files:
        rel = md_path.relative_to(PROJECT_ROOT)
        try:
            process_md_file(md_path, conn, output_dir=output_dir)
            processed += 1
        except SystemExit as e:
            print(f"  SKIPPED (collision): {rel}")
            print(f"    {e}\n")
            skipped += 1
        except Exception as e:
            print(f"  FAILED: {rel}")
            print(f"    {type(e).__name__}: {e}\n")
            failed += 1

    conn.close()

    print("\n" + "=" * 60)
    print(f"  Processed : {processed}")
    print(f"  Skipped   : {skipped}  (session_id already in target DB — use --overwrite to reset)")
    print(f"  Failed    : {failed}")
    print("=" * 60)

    if failed:
        print("\nReview failures above before sign-off.")
        sys.exit(1)

    print(f"\nJSON written to: {output_dir}")
    print("Review the output, then sign off by swapping directories:")
    print(f"  mv output_training_logs_json output_training_logs_json_old")
    print(f"  mv {output_dir.name} output_training_logs_json")


if __name__ == "__main__":
    main()
