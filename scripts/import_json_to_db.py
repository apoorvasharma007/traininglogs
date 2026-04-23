"""One-time script to import existing JSON session files into PostgreSQL."""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from traininglogs.db.db import get_connection, apply_schema
from traininglogs.db.insert import insert_session

OUTPUT_DIR = Path(__file__).parent.parent / "output_training_logs_json"


def main() -> None:
    conn = get_connection()
    apply_schema(conn)

    files = sorted(OUTPUT_DIR.rglob("*.json"))
    if not files:
        print("No JSON files found.")
        return

    inserted = 0
    skipped = 0

    for path in files:
        session = json.loads(path.read_text())
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM sessions WHERE session_id = %s", (session["session_id"],))
            already_exists = cur.fetchone() is not None

        if already_exists:
            skipped += 1
            print(f"  skipped (already exists): {session['session_id']}")
        else:
            insert_session(conn, session)
            inserted += 1
            print(f"  imported: {session['session_id']}")

    conn.close()
    print(f"\nDone. {inserted} imported, {skipped} skipped.")


if __name__ == "__main__":
    main()
