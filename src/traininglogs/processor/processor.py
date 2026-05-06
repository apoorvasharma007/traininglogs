"""
Processor: DATABASE_URL required, DB insert first, JSON write second.
On session_id collision the process errors — fix the date in the markdown and re-run.
"""
import hashlib
import json
import os
import sys
from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from traininglogs.parser.extract import TrainingMarkdownParser
from traininglogs.parser.parse import DeepTrainingParser
from traininglogs.db.db import get_connection, apply_schema
from traininglogs.db.insert import insert_session
from traininglogs.models.models import TrainingSession


LBS_TO_KG = 0.453592

PROJECT_ROOT = Path(__file__).resolve().parents[3]
INPUTS_DIR = PROJECT_ROOT / "inputs"
OUTPUT_DIR = PROJECT_ROOT / "output_training_logs_json"


def compute_session_id(md_path: Path, inputs_root: Path, date_str: str) -> str:
    """Deterministic session ID: YYYY-MM-DD-<6-char SHA256 of path relative to inputs_root>."""
    try:
        rel = md_path.relative_to(inputs_root)
    except ValueError:
        rel = Path(md_path.name)
    h = hashlib.sha256(str(rel).encode()).hexdigest()[:6]
    return f"{date_str}-{h}"


def _convert_lbs_to_kg(obj):
    if isinstance(obj, dict):
        return {
            k: round(v * LBS_TO_KG, 4) if k == "weight_kg" and isinstance(v, (int, float)) else _convert_lbs_to_kg(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_convert_lbs_to_kg(i) for i in obj]
    return obj


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


def process_md_file(
    md_path: Path,
    conn,
    inputs_root: Path | None = None,
    output_dir: Path = OUTPUT_DIR,
) -> TrainingSession:
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

    # Rename working_sets → sets (old field name → new) and inject set_type discriminator.
    # Also infer exercise_type from set contents so activity exercises are tagged correctly.
    for ex in primitive_dict.get("exercises", []):
        if "working_sets" in ex:
            raw_sets = ex.pop("working_sets") or []
            has_activity = False
            for s in raw_sets:
                if isinstance(s, dict):
                    if "set_type" not in s:
                        s["set_type"] = "strength"
                    elif s.get("set_type") == "activity":
                        has_activity = True
            ex["sets"] = raw_sets
            if has_activity:
                ex["exercise_type"] = "activity"

    weight_unit = intermediate["metadata"].get("unit", "kg").lower()
    if weight_unit == "lbs":
        primitive_dict = _convert_lbs_to_kg(primitive_dict)
        primitive_dict["weight_unit"] = "lbs"

    # Override session_id with the path-based deterministic scheme.
    date_str = intermediate["metadata"].get("date", primitive_dict.get("date", ""))
    _inputs_root = inputs_root if inputs_root is not None else INPUTS_DIR
    primitive_dict["session_id"] = compute_session_id(md_path, _inputs_root, date_str)

    session = TrainingSession.model_validate(primitive_dict)

    # DB insert first — a collision means the input date is wrong, not a silent skip
    if not insert_session(conn, session):
        raise SystemExit(
            f"\nERROR: session_id '{session.session_id}' already exists in the DB.\n"
            f"The date in '{md_path.name}' is likely wrong. Fix it and re-run.\n"
        )

    try:
        source_file: str | None = str(md_path.relative_to(PROJECT_ROOT))
    except ValueError:
        source_file = None
    if source_file:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET source_file = %s WHERE session_id = %s",
                (source_file, session.session_id),
            )
        conn.commit()

    print(f">>> Inserted into DB: {session.session_id}\n")

    # JSON write second — only after the DB confirms this is a new session
    week_dir = output_dir / session.program / f"phase {session.phase}" / f"week {session.week}"
    week_dir.mkdir(parents=True, exist_ok=True)

    output_path = week_dir / f"{session.session_id}.json"
    output_path.write_text(json.dumps(session.model_dump(mode="json"), indent=2))

    print(f">>> JSON written to: {output_path}\n")
    return session


