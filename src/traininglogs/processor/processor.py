"""
Processor: DATABASE_URL required, DB insert first, JSON write second.
On session_id collision the process errors — fix the date in the markdown and re-run.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

from traininglogs.parser.extract import TrainingMarkdownParser
from traininglogs.parser.parse import DeepTrainingParser
from traininglogs.db.db import get_connection
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


def _normalize_content(content: str) -> str:
    """Collapse whitespace differences that don't change what was written -- so the same
    text, retyped, re-copied with different line endings, or resubmitted with a trailing
    newline, is recognised as the same input."""
    return " ".join(content.split())


def compute_session_id(content: str, date_str: str) -> str:
    """Deterministic session ID: YYYY-MM-DD-<6-char SHA256 of the normalized content>.

    Identity is the text, not where it came from -- a file, pasted text, eventually a photo
    transcript, all hash the same way. Same input submitted twice, from any source, collides
    on this id and is caught by the same session_id check that already guards against
    accidental re-runs -- no separate dedup mechanism needed.

    This is a deliberate trade against the previous path-based scheme (decided 2026-08-10):
    editing a file's content and resubmitting is no longer treated as updating the same
    session in place -- it produces a new session_id, since the content changed. session_id
    was never guaranteed stable across code changes to begin with (see
    .claude/regen-historical.md -- it already happened once) -- compare on date, not
    session_id, when that matters."""
    h = hashlib.sha256(_normalize_content(content).encode()).hexdigest()[:6]
    return f"{date_str}-{h}"


_DEFAULT_USER_ID = "7"
_DEFAULT_USER_NAME = "Apoorva Sharma"
_DEFAULT_DATA_MODEL_VERSION = "0.0.1"
_DEFAULT_DATA_MODEL_TYPE = "TrainingSession"


def relative_source_file(md_path: Path) -> str | None:
    """The input's path relative to the repo, or None if it lives outside it.

    Shared by both parser paths so they cannot disagree about it — they did, and the AI path's
    version was "never set it at all"."""
    try:
        return str(md_path.relative_to(PROJECT_ROOT))
    except ValueError:
        return None


def build_session_from_extract(
    extract: "TrainingLogLLMExtract",  # noqa: F821 — avoid circular at module level
    content: str,
    md_path: Path | None = None,
    inputs_root: Path | None = None,
) -> TrainingSession:
    """Convert a confirmed TrainingLogLLMExtract to a TrainingSession.

    Injects system fields (session_id, user_id, user_name, data_model_version,
    data_model_type) that the LLM extract does not produce.

    `content` is the raw text that was captured -- used for session_id (see
    compute_session_id), so identity does not depend on there being a file at all.
    `md_path`, when given, only enriches program/phase/week from the file's directory
    position; a caller with no file (e.g. the API) omits it and gets neither, the same as
    an ad-hoc session today.
    """
    _inputs_root = inputs_root if inputs_root is not None else INPUTS_DIR
    session_dict = extract.model_dump(mode="python", exclude={"uncertain_fields"})

    if md_path is not None:
        path_ctx = _derive_program_context(md_path, _inputs_root)
        for key, value in path_ctx.items():
            if session_dict.get(key) is None:
                session_dict[key] = value

    session_dict["session_id"] = compute_session_id(content, extract.date)
    session_dict["user_id"] = _DEFAULT_USER_ID
    session_dict["user_name"] = _DEFAULT_USER_NAME
    session_dict["data_model_version"] = _DEFAULT_DATA_MODEL_VERSION
    session_dict["data_model_type"] = _DEFAULT_DATA_MODEL_TYPE

    return TrainingSession.model_validate(session_dict)


def _convert_lbs_to_kg(obj):
    if isinstance(obj, dict):
        return {
            k: round(v * LBS_TO_KG, 4) if k == "weight_kg" and isinstance(v, (int, float)) else _convert_lbs_to_kg(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_convert_lbs_to_kg(i) for i in obj]
    return obj


def write_session_json(session: TrainingSession, output_dir: Path | None) -> Path | None:
    """Write a session's JSON alongside the DB row, filed under program/phase/week.

    Shared by both parser paths so the same file lands in the same place regardless of which
    one produced it. Returns the path written, or None if `output_dir` is None.
    """
    if output_dir is None:
        return None
    if session.program and session.phase is not None and session.week is not None:
        week_dir = output_dir / session.program / f"phase {session.phase}" / f"week {session.week}"
    else:
        week_dir = output_dir / "sessions"
    week_dir.mkdir(parents=True, exist_ok=True)

    output_path = week_dir / f"{session.session_id}.json"
    output_path.write_text(json.dumps(session.model_dump(mode="json"), indent=2))
    print(f">>> JSON written to: {output_path}\n")
    return output_path


def process_md_file(
    md_path: Path,
    conn,
    inputs_root: Path | None = None,
    output_dir: Path | None = OUTPUT_DIR,
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
    session_dict["session_id"] = compute_session_id(md_text, date_str)

    session = TrainingSession.model_validate(session_dict)

    # DB insert first — a collision means the input date is wrong, not a silent skip
    if not insert_session(conn, session, source_file=relative_source_file(md_path)):
        raise SystemExit(
            f"\nERROR: session_id '{session.session_id}' already exists in the DB.\n"
            f"The date in '{md_path.name}' is likely wrong. Fix it and re-run.\n"
        )

    print(f">>> Inserted into DB: {session.session_id}\n")

    # JSON write second — only after the DB confirms this is a new session
    write_session_json(session, output_dir)
    return session
