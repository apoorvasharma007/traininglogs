"""Loads the shared exercise library: free-exercise-db's exercises, then ours, then nothing else.

Run by scripts/load_exercise_library.py, never by the server. Matches our exercises by exact
name, renames the 32 starter rows once (STARTER_RENAMES), and never deletes. The database checks
every value against the approved lists (migrations/0002_exercise_library.sql); this checks what
it can't.
"""
from __future__ import annotations

import json
from pathlib import Path

import psycopg2
import yaml
from psycopg2.extensions import cursor as Cursor

from traininglogs.db.ids import new_id

LIBRARY_FILE = Path(__file__).parent / "exercise_library.yaml"
# github.com/yuhonas/free-exercise-db, dist/exercises.json at this commit (they have no releases).
FREE_EXERCISE_DB_COMMIT = "f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5"
FREE_EXERCISE_DB_FILE = Path(__file__).parents[3] / "scripts" / "data" / "free_exercise_db.json"

# The starter rows 0001_baseline.sql adds, and the library exercise each becomes. The row keeps
# its id, so every link to it holds; the old name is one of the new exercise's other names.
STARTER_RENAMES = {
    "Barbell Back Squat": "Squat (Barbell)",
    "Barbell Front Squat": "Front Squat (Barbell)",
    "Barbell Bench Press": "Bench Press (Barbell)",
    "Incline Barbell Bench Press": "Incline Press (Barbell)",
    "Dumbbell Bench Press": "Bench Press (Dumbbell)",
    "Incline Dumbbell Press": "Incline Press (Dumbbell, 45 Degree)",
    "Barbell Overhead Press": "Overhead Press (Barbell)",
    "Dumbbell Shoulder Press": "Shoulder Press (Dumbbell, Seated)",
    "Barbell Deadlift": "Deadlift (Barbell)",
    "Romanian Deadlift": "Romanian Deadlift (Barbell)",
    "Barbell Row": "Row (Barbell)",
    "Dumbbell Row": "Row (Dumbbell, Single Arm)",
    "Pull-up": "Pull-up (Bodyweight)",
    "Chin-up": "Chin-up (Bodyweight)",
    "Lat Pulldown": "Lat Pulldown (Cable, Wide Grip)",
    "Seated Cable Row": "Row (Cable, Seated, Neutral Grip)",
    "Dip": "Dip (Bodyweight)",
    "Push-up": "Push-up (Bodyweight)",
    "Leg Press": "Leg Press (Machine)",
    "Leg Extension": "Leg Extension (Machine)",
    "Leg Curl": "Leg Curl (Machine, Lying)",
    "Standing Calf Raise": "Calf Raise (Machine, Standing)",
    "Walking Lunge": "Walking Lunge (Dumbbell)",
    "Hip Thrust": "Hip Thrust (Barbell)",
    "Barbell Curl": "Biceps Curl (Barbell)",
    "Dumbbell Curl": "Biceps Curl (Dumbbell)",
    "Triceps Pushdown": "Triceps Pressdown (Cable, Bar)",
    "Lateral Raise": "Lateral Raise (Dumbbell)",
    "Face Pull": "Face Pull (Cable)",
    "Power Clean": "Power Clean (Barbell)",
    "Kettlebell Swing": "Swing (Kettlebell)",
    "Plank": "Plank (Bodyweight)",
}

FIELDS = [
    "equipment", "other_names", "measures", "compound", "primary_muscles", "secondary_muscles",
    "joint_actions", "movement_patterns", "free_exercise_db_id",
]
ARRAYS = {"other_names", "measures", "primary_muscles", "secondary_muscles", "joint_actions", "movement_patterns"}
REQUIRED = ["name", "equipment", "measures", "primary_muscles"]
THEIR_FIELDS = {
    "id": "id", "name": "name", "force": "force", "level": "level", "mechanic": "mechanic",
    "equipment": "equipment", "category": "category", "primary_muscles": "primaryMuscles",
    "secondary_muscles": "secondaryMuscles", "instructions": "instructions", "images": "images",
}


class LibraryError(Exception):
    """The file can't be loaded; the message lists every problem found."""


def read_library() -> list[dict]:
    return yaml.safe_load(LIBRARY_FILE.read_text())


def read_free_exercise_db() -> list[dict]:
    return json.loads(FREE_EXERCISE_DB_FILE.read_text())


def check_library(library: list[dict]) -> list[str]:
    """Problems the database can't see: missing required fields, a name used twice, an other
    name not in lower case, a rename whose old name isn't an other name. Other names are search
    words, so one can be on several exercises."""
    problems = []
    names = [e.get("name") for e in library]
    for e in library:
        for field in REQUIRED:
            if not e.get(field):
                problems.append(f"{e.get('name', '(no name)')}: {field} is required")
        for field in set(e) - set(FIELDS) - {"name"}:
            problems.append(f"{e.get('name')}: unknown field {field}")
    # Unique ignoring case: the server links a typed name by its lower case.
    lowered = [str(n).lower() for n in names]
    for name in {n for n in names if lowered.count(str(n).lower()) > 1}:
        problems.append(f"{name}: in the file more than once (ignoring case)")
    for e in library:
        for other in e.get("other_names") or []:
            if other != other.lower():
                problems.append(f"{e['name']}: other name {other!r} isn't lower case")
    by_name = {e.get("name"): e for e in library}
    for old, new in STARTER_RENAMES.items():
        if new not in by_name:
            problems.append(f"{new}: starter row {old!r} is renamed to it, but it isn't in the file")
        elif old.lower() not in (by_name[new].get("other_names") or []):
            problems.append(f"{new}: needs {old.lower()!r} in its other names (the starter row's name)")
    return problems


def load_free_exercise_db(cur: Cursor, rows: list[dict]) -> dict[str, list[str]]:
    """Adds their new exercises and updates changed ones. Never deletes."""
    cols = list(THEIR_FIELDS)
    cur.execute(f"SELECT {', '.join(cols)} FROM free_exercise_db")
    stored = {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}
    report: dict[str, list[str]] = {"added": [], "updated": [], "not_in_file": []}
    for row in rows:
        values = {col: row.get(theirs) for col, theirs in THEIR_FIELDS.items()}
        if values["id"] not in stored:
            cur.execute(
                f"INSERT INTO free_exercise_db ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                [values[c] for c in cols],
            )
            report["added"].append(values["id"])
        elif stored[values["id"]] != values:
            cur.execute(
                f"UPDATE free_exercise_db SET {', '.join(f'{c} = %s' for c in cols[1:])} WHERE id = %s",
                [values[c] for c in cols[1:]] + [values["id"]],
            )
            report["updated"].append(values["id"])
    report["not_in_file"] = sorted(set(stored) - {r["id"] for r in rows})
    return report


def load_library(cur: Cursor, library: list[dict]) -> dict[str, list[str]]:
    """Renames the starter rows, then adds or updates every exercise in the file by name. Rows
    the file doesn't have are reported, never deleted. Raises LibraryError before writing
    anything if the file has problems."""
    problems = check_library(library)
    if problems:
        raise LibraryError("\n".join(problems))

    report: dict[str, list[str]] = {"renamed": [], "added": [], "updated": [], "not_in_file": []}
    cur.execute("SELECT name FROM library_exercises")
    stored_names = {r[0] for r in cur.fetchall()}
    for old, new in STARTER_RENAMES.items():
        if old not in stored_names:
            continue
        if new in stored_names:
            raise LibraryError(f"Can't rename {old!r}: {new!r} is already a separate row")
        cur.execute("UPDATE library_exercises SET name = %s, updated_at = now() WHERE name = %s", (new, old))
        report["renamed"].append(f"{old} -> {new}")

    # The list columns are domains psycopg2 doesn't know; cast them so they read as lists.
    cur.execute(f"SELECT name, {', '.join(f + '::text[]' if f in ARRAYS else f for f in FIELDS)} FROM library_exercises")
    stored = {r[0]: dict(zip(FIELDS, r[1:])) for r in cur.fetchall()}
    for e in library:
        values = {f: e.get(f) for f in FIELDS}
        for f in ("other_names", "secondary_muscles", "joint_actions", "movement_patterns"):
            values[f] = values[f] or []
        try:
            _write(cur, e["name"], values, stored.get(e["name"]), report)
        except psycopg2.Error as err:
            raise LibraryError(f"{e['name']}: the database refused it: {err.pgerror.strip()}") from err
    report["not_in_file"] = sorted(set(stored) - {e["name"] for e in library})
    return report


def _write(cur: Cursor, name: str, values: dict, stored: dict | None, report: dict[str, list[str]]) -> None:
    if stored is None:
        cur.execute(
            f"INSERT INTO library_exercises (id, name, {', '.join(FIELDS)})"
            f" VALUES (%s, %s, {', '.join(['%s'] * len(FIELDS))})",
            [new_id(), name] + [values[f] for f in FIELDS],
        )
        report["added"].append(name)
        return
    changed = [f for f in FIELDS if stored[f] != values[f]]
    if changed:
        cur.execute(
            f"UPDATE library_exercises SET {', '.join(f'{f} = %s' for f in FIELDS)}, updated_at = now()"
            " WHERE name = %s",
            [values[f] for f in FIELDS] + [name],
        )
        report["updated"].append(f"{name} ({', '.join(changed)})")
