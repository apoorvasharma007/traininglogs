"""
Processor: DATABASE_URL required, DB insert first, JSON write second.
On session_id collision the process errors — fix the date in the markdown and re-run.
"""
import hashlib
import json
import os
import re
import sys
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

_PHASE_RE = re.compile(r"^phase[_\s]?(\d+)$", re.IGNORECASE)
_WEEK_RE  = re.compile(r"^week[_\s]?(\d+)$",  re.IGNORECASE)


def _derive_program_context(md_path: Path, inputs_root: Path) -> dict:
    """Infer program/phase/week from directory structure when not in file metadata.

    Expects: inputs_root/programs/<slug>/phase_N/week_N/<file>.md
    Returns a dict with only the fields that could be derived (may be empty).
    """
    try:
        rel = md_path.relative_to(inputs_root)
    except ValueError:
        return {}

    parts = rel.parts  # e.g. ('programs', 'slug', 'phase_3', 'week_11', 'file.md')
    if len(parts) < 5 or parts[0] != "programs":
        return {}

    slug = parts[1]
    phase_m = _PHASE_RE.match(parts[2])
    week_m  = _WEEK_RE.match(parts[3])
    if not phase_m or not week_m:
        return {}

    return {
        "program": slug,
        "phase":   int(phase_m.group(1)),
        "week":    int(week_m.group(1)),
    }


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
    session_dict = deep_parser.build_training_session()

    # Enrich with path-derived program context for any fields the file omitted.
    # Explicit metadata in the file always wins; path is the fallback.
    _inputs_root = inputs_root if inputs_root is not None else INPUTS_DIR
    path_ctx = _derive_program_context(md_path, _inputs_root)
    for key, value in path_ctx.items():
        if session_dict.get(key) is None:
            session_dict[key] = value

    weight_unit = intermediate["metadata"].get("unit", "kg").lower()
    if weight_unit == "lbs":
        session_dict = _convert_lbs_to_kg(session_dict)
        session_dict["weight_unit"] = "lbs"

    date_str = intermediate["metadata"].get("date", session_dict.get("date", ""))
    session_dict["session_id"] = compute_session_id(md_path, _inputs_root, date_str)

    session = TrainingSession.model_validate(session_dict)

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
    if session.program and session.phase is not None and session.week is not None:
        week_dir = output_dir / session.program / f"phase {session.phase}" / f"week {session.week}"
    else:
        week_dir = output_dir / "sessions"
    week_dir.mkdir(parents=True, exist_ok=True)

    output_path = week_dir / f"{session.session_id}.json"
    output_path.write_text(json.dumps(session.model_dump(mode="json"), indent=2))

    print(f">>> JSON written to: {output_path}\n")
    return session
