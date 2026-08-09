"""Truncate a DB and repopulate from all .md input files.

Destructive — truncates all session data and reimports from scratch.

Normal use (prod DB):
  .venv/bin/python scripts/repopulate_db.py

Validation use (validation DB at port 5434):
  .venv/bin/python scripts/repopulate_db.py --regen --no-json

  --no-json skips writing output_training_logs_json/ so JSON regen stays a
  deliberate separate step (Step 7) rather than a side-effect of DB validation.

Safety guards:
  - Refuses to run against the test DB (port 5433 / traininglogs_test).
  - --regen mode uses REGEN_DATABASE_URL; refuses if it looks like prod or test.
  - Normal mode uses DATABASE_URL; refuses if it looks like test or regen DB.
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from traininglogs.db.db import get_connection, apply_schema
from traininglogs.processor.processor import process_md_file

PROJECT_ROOT = Path(__file__).parent.parent
INPUTS_DIR = PROJECT_ROOT / "inputs"
OUTPUT_DIR = PROJECT_ROOT / "output_training_logs_json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--regen",
        action="store_true",
        help="Use REGEN_DATABASE_URL (port 5434 validation DB) instead of DATABASE_URL",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Skip writing output_training_logs_json/ — use during DB validation to avoid premature JSON regen",
    )
    args = parser.parse_args()

    if args.regen:
        db_url = os.environ.get("REGEN_DATABASE_URL", "")
        if not db_url:
            print("ERROR: REGEN_DATABASE_URL is not set.")
            sys.exit(1)
        if "traininglogs_test" in db_url or "5433" in db_url:
            print("ERROR: REGEN_DATABASE_URL looks like the test DB. Refusing.")
            sys.exit(1)
        if "5434" not in db_url and "traininglogs_regen" not in db_url:
            print("ERROR: REGEN_DATABASE_URL must target the regen DB (port 5434 or traininglogs_regen).")
            print("Use --regen only with the db_regen service at port 5434.")
            sys.exit(1)
    else:
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            print("ERROR: DATABASE_URL is not set.")
            sys.exit(1)
        if "traininglogs_test" in db_url or "5433" in db_url:
            print("ERROR: DATABASE_URL looks like the test DB. Refusing.")
            sys.exit(1)
        if "5434" in db_url or "traininglogs_regen" in db_url:
            print("ERROR: DATABASE_URL looks like the regen DB. Use --regen flag.")
            sys.exit(1)

    conn = get_connection(db_url)
    apply_schema(conn)

    print("Truncating sessions (cascades to exercises, working_sets, warmup_sets)...")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE sessions CASCADE")
    conn.commit()
    print("Truncated.\n")

    md_files = sorted(f for f in INPUTS_DIR.rglob("*.md") if f.name != "program.md")
    print(f"Found {len(md_files)} .md files under {INPUTS_DIR}\n")

    inserted = 0
    failed = 0

    for md_path in md_files:
        try:
            process_md_file(
                md_path, conn,
                inputs_root=INPUTS_DIR,
                output_dir=None if args.no_json else OUTPUT_DIR,
            )
            inserted += 1
        except SystemExit as e:
            print(f"  ERROR (SystemExit): {md_path.name} — {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {md_path.name} — {e}")
            failed += 1

    conn.close()
    print(f"\nDone. {inserted} inserted, {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
