"""Building a program from logged sessions, against the real test DB."""
from __future__ import annotations

import os

import pytest

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.insert import insert_session
from traininglogs.db.programs import get_program
from traininglogs.ingest.program_history import HistoryProgram, build_from_history
from traininglogs.models.models import TrainingSession

from signed_in import USER_A

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)
SOURCE = "history-test-program"
PROGRAM = HistoryProgram("History test", SOURCE, (1, 2), 3, 1, ("Upper", "Lower"))


def _session(sid: str, day: str, week: int, focus: str, phase: int = 3) -> TrainingSession:
    return TrainingSession.model_validate({
        "data_model_version": "0.0.1", "data_model_type": "TrainingSession",
        "session_id": sid, "user_id": "7", "user_name": "Apoorva Sharma", "date": day,
        "program": SOURCE, "phase": phase, "week": week, "focus": focus,
        "exercises": [
            {"number": 1, "name": "Incline  DB Press", "current_goal": {"sets": 3, "rep_range": {"min": 8, "max": 10}},
             "warmup_sets": [{"number": 1, "weight_kg": 20.0}],
             "sets": [{"number": 1, "weight_kg": 30.0, "rep_count": {"full": 9, "partial": 0}}]},
            {"number": 2, "name": "Pec Dec",
             "sets": [{"number": n, "weight_kg": 50.0, "rep_count": {"full": 12, "partial": 0}} for n in (1, 2)]},
        ],
    })


def _clean(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE program = %s", (SOURCE,))
        cur.execute(
            "DELETE FROM program_workout_exercises WHERE workout_id IN (SELECT w.id FROM program_workouts w "
            "JOIN programs p ON p.id = w.program_id WHERE p.name = %s)", (PROGRAM.name,))
        cur.execute("DELETE FROM program_workouts WHERE program_id IN (SELECT id FROM programs WHERE name = %s)", (PROGRAM.name,))
        cur.execute("DELETE FROM programs WHERE name = %s", (PROGRAM.name,))
    conn.commit()


@pytest.fixture()
def conn():
    c = get_connection(TEST_DB_URL)
    apply_schema(c)
    _clean(c)
    for i, (day, week, focus, phase) in enumerate([
        ("3002-01-05", 1, "Upper", 3), ("3002-01-06", 1, "Lower", 3),
        ("3002-01-12", 2, "Upper", 3), ("3001-06-01", 1, "Upper", 2),
        ("3002-02-20", 7, "Upper", 3),  # outside weeks 1-2: not linked
    ]):
        insert_session(c, _session(f"history-test-{i}", day, week, focus, phase), user_id=USER_A)
    yield c
    _clean(c)
    c.close()


def test_plan_comes_from_the_chosen_week_and_sessions_are_linked(conn) -> None:
    summary = build_from_history(conn, PROGRAM, USER_A)
    assert [(w["focus"], w["sessions_linked"]) for w in summary["workouts"]] == [("Upper", 3), ("Lower", 1)]

    program = get_program(conn, summary["program_id"])
    assert [(w["position"], w["name"]) for w in program["workouts"]] == [(1, "Upper"), (2, "Lower")]
    assert program["workouts"][0]["exercises"] == [
        {"name": "Incline DB Press", "warmup_sets": 1, "working_sets": 3, "target_reps": 10, "amrap": False, "alternatives": []},
        {"name": "Pec Dec", "warmup_sets": 0, "working_sets": 2, "target_reps": None, "amrap": False, "alternatives": []},
    ]
    assert program["workouts"][0]["last_done"].isoformat() == "3002-01-12"
    # The latest linked session is Upper in week 2, so Lower comes next.
    assert program["next_workout_id"] == program["workouts"][1]["id"]
    assert program["following"] is False


def test_refuses_to_build_twice(conn) -> None:
    build_from_history(conn, PROGRAM, USER_A)
    with pytest.raises(ValueError, match="already exists"):
        build_from_history(conn, PROGRAM, USER_A)


def test_refuses_when_the_plan_week_has_no_session(conn) -> None:
    with pytest.raises(ValueError, match="No sessions"):
        build_from_history(conn, HistoryProgram("History test", SOURCE, (1,), 3, 5, ("Upper",)), USER_A)
