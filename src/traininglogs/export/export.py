"""Export: everything a person has logged, as a CSV of sets or as JSON. Built from
`db.fetch.get_export_rows` (one row per set) and their programs."""
from __future__ import annotations

import csv
import io
from decimal import Decimal
from typing import Any

CSV_COLUMNS = [
    "date", "session", "program", "exercise_number", "exercise", "set_kind", "set_number",
    "weight_kg", "reps", "reps_partial", "rpe", "duration_seconds", "distance_meters",
    "set_notes", "exercise_notes", "session_notes",
]


def _session_name(row: dict) -> str:
    if row["workout_position"] is not None:
        return row["workout_name"] or f"Workout {row['workout_position']}"
    return row["focus"] or ""


def _plain(value: Any) -> Any:
    """Numbers as numbers (2.5, not Decimal('2.5')), dates as YYYY-MM-DD."""
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def to_csv(rows: list[dict]) -> str:
    """One line per set, oldest first. Opens in Excel, Numbers or Google Sheets."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({
            **{k: _plain(r.get(k)) for k in CSV_COLUMNS},
            "session": _session_name(r),
            "program": r["program_name"] or r["program"] or "",
        })
    return out.getvalue()


def to_json(rows: list[dict], programs: list[dict], app_version: str, exported_at: str) -> dict:
    """Sessions with their exercises and sets, and the person's programs, as one document."""
    sessions: dict[str, dict] = {}
    for r in rows:
        s = sessions.setdefault(r["session_id"], {
            "date": _plain(r["date"]), "name": _session_name(r),
            "program": r["program_name"] or r["program"], "duration_minutes": r["duration_minutes"],
            "notes": r["session_notes"], "exercises": [],
        })
        if r["exercise"] is None:
            continue
        if not s["exercises"] or s["exercises"][-1]["number"] != r["exercise_number"]:
            s["exercises"].append({"number": r["exercise_number"], "name": r["exercise"], "notes": r["exercise_notes"], "sets": []})
        if r["set_kind"] is not None:
            s["exercises"][-1]["sets"].append({
                "kind": r["set_kind"], "number": r["set_number"], "weight_kg": _plain(r["weight_kg"]),
                "reps": r["reps"], "reps_partial": r["reps_partial"], "rpe": _plain(r["rpe"]),
                "duration_seconds": r["duration_seconds"], "distance_meters": _plain(r["distance_meters"]),
                "notes": r["set_notes"],
            })
    return {
        "exported_at": exported_at,
        "app_version": app_version,
        "sessions": list(sessions.values()),
        "programs": [
            {"name": p["name"], "following": p["following"], "workouts": [
                {"position": w["position"], "name": w["name"], "warmup": w["warmup"], "cooldown": w["cooldown"],
                 "exercises": w["exercises"]} for w in p["workouts"]]}
            for p in programs
        ],
    }
