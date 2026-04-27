"""
Processor v2: DATABASE_URL required, DB insert first, JSON write second.
On session_id collision the process errors — fix the date in the markdown and re-run.
"""
import json
import os
import sys
import argparse
from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from traininglogs.parser.extract import TrainingMarkdownParser
from traininglogs.parser.parse import DeepTrainingParser
from traininglogs.db.db import get_connection, apply_schema
from traininglogs.db.insert_v2 import insert_session
from traininglogs.models.models_v2 import TrainingSession


def _to_primitive(o):
    if isinstance(o, Enum):
        return o.value
    if is_dataclass(o):
        return {k: _to_primitive(getattr(o, k)) for k in o.__dataclass_fields__}
    if isinstance(o, list):
        return [_to_primitive(i) for i in o]
    if isinstance(o, dict):
        return {k: _to_primitive(v) for k, v in o.items()}
    return o


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INPUT_LOGS_DIR = PROJECT_ROOT / "input_training_logs_md"
OUTPUT_DIR = PROJECT_ROOT / "output_training_logs_json"


def process_md_file(md_path: Path, conn, output_dir: Path = OUTPUT_DIR) -> TrainingSession:
    """Parse a markdown file, insert to DB, then write JSON.

    Returns the inserted TrainingSession.
    Raises SystemExit if session_id already exists in the DB.
    """
    md_text = md_path.read_text(encoding="utf-8")
    print(f">>> Loaded training log: {md_path}\n")

    base_parser = TrainingMarkdownParser(md_text)
    intermediate = base_parser.parse()

    deep_parser = DeepTrainingParser(intermediate)
    session_obj = deep_parser.build_training_session()

    # Bridge: dataclass → Pydantic (parser still returns old dataclass models)
    primitive_dict = _to_primitive(session_obj)
    session = TrainingSession.model_validate(primitive_dict)

    # DB insert first — a collision means the input date is wrong, not a silent skip
    if not insert_session(conn, session):
        raise SystemExit(
            f"\nERROR: session_id '{session.session_id}' already exists in the DB.\n"
            f"The date in '{md_path.name}' is likely wrong. Fix it and re-run.\n"
        )

    print(f">>> Inserted into DB: {session.session_id}\n")

    # JSON write second — only after the DB confirms this is a new session
    week_dir = output_dir / session.program / f"phase {session.phase}" / f"week {session.week}"
    week_dir.mkdir(parents=True, exist_ok=True)

    output_path = week_dir / f"{session.session_id}.json"
    output_path.write_text(json.dumps(primitive_dict, indent=2))

    print(f">>> JSON written to: {output_path}\n")
    return session


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "ERROR: DATABASE_URL is not set.\n"
            "Start Postgres with 'docker compose up -d' and set DATABASE_URL in .env",
            file=sys.stderr,
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Process training logs for a given phase and week."
    )
    parser.add_argument("--phase", type=int, required=True, help="Phase number")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    args = parser.parse_args()

    raw_logs_dir = INPUT_LOGS_DIR / f"phase {args.phase} week {args.week}"
    if not raw_logs_dir.exists():
        print(f"ERROR: directory not found: {raw_logs_dir}", file=sys.stderr)
        sys.exit(1)

    md_files = list(raw_logs_dir.glob("*.md"))
    if not md_files:
        print(f"ERROR: no markdown files found in {raw_logs_dir}", file=sys.stderr)
        sys.exit(1)

    conn = get_connection()
    apply_schema(conn)
    try:
        for md_path in md_files:
            process_md_file(md_path, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
