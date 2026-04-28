"""Import JSON session files into PostgreSQL using Pydantic models. Use --overwrite to reimport all."""
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.insert_v2 import insert_session
from traininglogs.models.models_v2 import TrainingSession

OUTPUT_DIR = Path(__file__).parent.parent / "output_training_logs_json"


def import_sessions(
    conn,
    output_dir: Path,
    overwrite: bool = False,
) -> tuple[int, int, int]:
    """Validate and import all JSON session files from output_dir into the DB.

    Returns (inserted, skipped, failed) counts.
    """
    if overwrite:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE sessions CASCADE")
        conn.commit()
        print("Truncated sessions (cascaded to exercises, working_sets, warmup_sets).")

    files = sorted(output_dir.rglob("*.json"))
    if not files:
        print("No JSON files found.")
        return 0, 0, 0

    inserted = 0
    skipped = 0
    failed = 0

    for path in files:
        raw = json.loads(path.read_text())

        try:
            session = TrainingSession.model_validate(raw)
        except ValidationError as exc:
            failed += 1
            print(f"  VALIDATION ERROR: {path.name}")
            print(f"    {exc}")
            continue

        if insert_session(conn, session):
            inserted += 1
            print(f"  imported: {session.session_id}")
        else:
            skipped += 1
            print(f"  skipped (already exists): {session.session_id}")

    return inserted, skipped, failed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import JSON session files into PostgreSQL using Pydantic models."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Truncate all tables and reimport from scratch",
    )
    args = parser.parse_args()

    conn = get_connection()
    apply_schema(conn)

    inserted, skipped, failed = import_sessions(conn, OUTPUT_DIR, overwrite=args.overwrite)
    conn.close()

    print(f"\nDone. {inserted} imported, {skipped} skipped, {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
