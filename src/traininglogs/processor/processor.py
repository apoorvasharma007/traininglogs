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


def compute_session_id(md_path: Path, inputs_root: Path, date_str: str) -> str:
    """Deterministic session ID: YYYY-MM-DD-<6-char SHA256 of path relative to inputs_root>."""
    try:
        rel = md_path.relative_to(inputs_root)
    except ValueError:
        rel = Path(md_path.name)
    h = hashlib.sha256(str(rel).encode()).hexdigest()[:6]
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
    md_path: Path,
    inputs_root: Path | None = None,
) -> TrainingSession:
    """Convert a confirmed TrainingLogLLMExtract to a TrainingSession.

    Injects system fields (session_id, user_id, user_name, data_model_version,
    data_model_type) that the LLM extract does not produce.
    """
    _inputs_root = inputs_root if inputs_root is not None else INPUTS_DIR
    session_dict = extract.model_dump(mode="python", exclude={"uncertain_fields"})

    path_ctx = _derive_program_context(md_path, _inputs_root)
    for key, value in path_ctx.items():
        if session_dict.get(key) is None:
            session_dict[key] = value

    session_dict["session_id"] = compute_session_id(md_path, _inputs_root, extract.date)
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
    session_dict["session_id"] = compute_session_id(md_path, _inputs_root, date_str)

    session = TrainingSession.model_validate(session_dict)

    # DB insert first — a collision means the input date is wrong, not a silent skip
    if not insert_session(conn, session, source_file=relative_source_file(md_path)):
        raise SystemExit(
            f"\nERROR: session_id '{session.session_id}' already exists in the DB.\n"
            f"The date in '{md_path.name}' is likely wrong. Fix it and re-run.\n"
        )

    print(f">>> Inserted into DB: {session.session_id}\n")

    # JSON write second — only after the DB confirms this is a new session
    if output_dir is not None:
        if session.program and session.phase is not None and session.week is not None:
            week_dir = output_dir / session.program / f"phase {session.phase}" / f"week {session.week}"
        else:
            week_dir = output_dir / "sessions"
        week_dir.mkdir(parents=True, exist_ok=True)

        output_path = week_dir / f"{session.session_id}.json"
        output_path.write_text(json.dumps(session.model_dump(mode="json"), indent=2))

        print(f">>> JSON written to: {output_path}\n")
    return session


def process_md_file_with_ai(
    md_path: Path,
    conn,
    orchestrator=None,
    model: str | None = None,
    inputs_root: Path | None = None,
    output_dir: Path | None = OUTPUT_DIR,
) -> TrainingSession:
    """The AI parser path: capture the text, extract from it, store both, then the session.

    Lives here beside process_md_file rather than nested inside the CLI, where it had no test.
    That is not incidental — `source_file` was set by the rules path and silently never set by
    this one, so every AI-parsed session in the database has no link to the text it came from,
    and nothing could have caught it.

    `orchestrator` and `model` exist so a test can drive this without an API call. Left unset,
    the real provider is built here so that the model which actually did the work is what gets
    recorded.
    """
    import json

    from traininglogs.agent.prompts import PROMPT_VERSION
    from traininglogs.db.insert import insert_extraction, insert_raw_input

    _inputs_root = inputs_root if inputs_root is not None else INPUTS_DIR
    md_text = md_path.read_text(encoding="utf-8")
    source_file = relative_source_file(md_path)

    # Stored before anything is asked of the model. If extraction fails, or the session is
    # rejected at the confirmation card, what the person wrote is already kept — a capture layer
    # that depends on interpretation succeeding is not a capture layer.
    raw_input_id = insert_raw_input(
        conn, md_text, source_kind="markdown", source_file=source_file
    )

    if orchestrator is None:
        from traininglogs.agent.llm_orchestrator import LLMOrchestrator
        from traininglogs.agent.providers import AnthropicProvider

        provider = AnthropicProvider()
        orchestrator = LLMOrchestrator(parser_provider=provider)
        model = model or provider.model

    extract = orchestrator.run(md_text)

    # run() only returns once the card has been confirmed, so this is not pending.
    extraction_id = insert_extraction(
        conn,
        raw_input_id=raw_input_id,
        model=model or "unknown",
        prompt_version=PROMPT_VERSION,
        extract=extract.model_dump(mode="json"),
        uncertain_fields=list(extract.uncertain_fields or []),
        warnings=list(extract.warnings or []),
        status="confirmed",
    )

    session = build_session_from_extract(extract, md_path, _inputs_root)

    if not insert_session(
        conn, session, source_file=source_file, extraction_id=extraction_id
    ):
        raise SystemExit(
            f"\nERROR: session_id '{session.session_id}' already exists in the DB.\n"
            f"The date in '{md_path.name}' is likely wrong. Fix it and re-run.\n"
        )

    print(f">>> Inserted into DB: {session.session_id}\n")

    if output_dir is not None:
        if session.program and session.phase is not None and session.week is not None:
            week_dir = output_dir / session.program / f"phase {session.phase}" / f"week {session.week}"
        else:
            week_dir = output_dir / "sessions"
        week_dir.mkdir(parents=True, exist_ok=True)
        output_path = week_dir / f"{session.session_id}.json"
        output_path.write_text(json.dumps(session.model_dump(mode="json"), indent=2))
        print(f">>> JSON written to: {output_path}\n")

    return session
