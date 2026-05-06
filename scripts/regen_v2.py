"""Regenerate all historical JSON files using the current processor_v2 pipeline.

Safety-isolated: writes to output_training_logs_json_v2/ and inserts into the
traininglogs_validation DB — never touches the live output dir or prod/test DBs.

Usage:
    python scripts/regen_v2.py [--overwrite] [--db-url URL] [--output-dir DIR]

Run docker compose up -d db_validation before running this script.
After reviewing output, sign off manually before swapping dirs:
    mv output_training_logs_json output_training_logs_json_old
    mv output_training_logs_json_v2 output_training_logs_json
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
from traininglogs.db.insert_v2 import insert_session
from traininglogs.processor.processor_v2 import process_md_file

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output_training_logs_json_v2"
INPUT_DIR = PROJECT_ROOT / "input_training_logs_md"

VALIDATION_DB_URL = (
    os.environ.get("VALIDATION_DATABASE_URL")
    or "postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate historical JSON files via processor_v2.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Truncate the validation DB before running (safe to re-run from scratch).",
    )
    parser.add_argument(
        "--db-url",
        default=VALIDATION_DB_URL,
        help="Validation DB URL (default: VALIDATION_DATABASE_URL env var or port 5434).",
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

    conn = get_connection(args.db_url)
    apply_schema(conn)

    if args.overwrite:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE sessions CASCADE")
        conn.commit()
        print("Truncated validation DB (cascaded to all child tables).")

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
            # process_md_file raises SystemExit on session_id collision.
            # In the validation run this is a skip — the session was already
            # inserted on a previous run (or --overwrite wasn't passed).
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
    print(f"  Skipped   : {skipped}  (session_id already in validation DB)")
    print(f"  Failed    : {failed}   (parse or model error)")
    print("=" * 60)

    if failed:
        print("\nReview failures above before sign-off.")
        sys.exit(1)

    print(f"\nJSON written to: {output_dir}")
    print("Review the output, then sign off by swapping directories:")
    print("  mv output_training_logs_json output_training_logs_json_old")
    print("  mv output_training_logs_json_v2 output_training_logs_json")


if __name__ == "__main__":
    main()
