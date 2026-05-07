"""Truncate the prod DB and repopulate from all .md input files.

Destructive — truncates all session data and reimports from scratch.
Run with DATABASE_URL pointing to the prod DB:
  .venv/bin/python scripts/repopulate_db.py

Safety guard: refuses to run if DATABASE_URL looks like the test DB.
"""
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
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL is not set.")
        sys.exit(1)
    if "traininglogs_test" in db_url or "5433" in db_url:
        print("ERROR: DATABASE_URL looks like the test DB.")
        print(f"  Got: {db_url!r}")
        print("Refusing to truncate the test DB.")
        sys.exit(1)

    conn = get_connection()
    apply_schema(conn)

    print("Truncating sessions (cascades to exercises, working_sets, warmup_sets)...")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE sessions CASCADE")
    conn.commit()
    print("Truncated.\n")

    md_files = sorted(INPUTS_DIR.rglob("*.md"))
    print(f"Found {len(md_files)} .md files under {INPUTS_DIR}\n")

    inserted = 0
    failed = 0

    for md_path in md_files:
        try:
            process_md_file(md_path, conn, inputs_root=INPUTS_DIR, output_dir=OUTPUT_DIR)
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
