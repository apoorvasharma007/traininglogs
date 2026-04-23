import json
import os
import pytest
import psycopg2

from traininglogs.db.db import get_connection, apply_schema
from traininglogs.db.insert import insert_session

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)

MINIMAL_SESSION = {
    "session_id": "test-session-001",
    "user_id": "7",
    "user_name": "Apoorva Sharma",
    "date": "2026-01-01",
    "program": "Test Program",
    "program_author": "Test Author",
    "program_length_weeks": 12,
    "phase": 1,
    "week": 1,
    "is_deload_week": False,
    "focus": "Push",
    "session_duration_minutes": 60,
    "exercises": [
        {
            "number": 1,
            "name": "Bench Press",
            "notes": "felt strong",
            "warmup_notes": "Pyramid",
            "form_cues": ["brace core", "retract scapula"],
            "target_muscle_groups": None,
            "rep_tempo": None,
            "current_goal": {
                "weight_kg": 80.0,
                "sets": 3,
                "rep_range": {"min": 5, "max": 6},
                "rest_minutes": 2,
            },
            "warmup_sets": [
                {"number": 1, "weight_kg": 60.0, "rep_count": 5, "notes": None}
            ],
            "working_sets": [
                {
                    "number": 1,
                    "weight_kg": 80.0,
                    "rep_count": {"full": 5, "partial": 0},
                    "rpe": 8.0,
                    "rep_quality_assessment": "good",
                    "actual_rest_minutes": None,
                    "notes": None,
                    "failure_technique": None,
                },
                {
                    "number": 2,
                    "weight_kg": 80.0,
                    "rep_count": {"full": 4, "partial": 1},
                    "rpe": 10.0,
                    "rep_quality_assessment": "perfect",
                    "actual_rest_minutes": None,
                    "notes": "last rep was a grind",
                    "failure_technique": {
                        "technique_type": "MyoReps",
                        "details": {
                            "mini_sets": [
                                {"number": 1, "rep_count": {"full": 3, "partial": 0}}
                            ]
                        },
                    },
                },
            ],
        }
    ],
}


@pytest.fixture(scope="module")
def conn():
    c = get_connection(TEST_DB_URL)
    apply_schema(c)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def clean_db(conn):
    yield
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sessions")
    conn.commit()


def test_insert_session_creates_all_rows(conn):
    insert_session(conn, MINIMAL_SESSION)

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM sessions WHERE session_id = %s", ("test-session-001",))
        session = cur.fetchone()
        assert session is not None

        cur.execute("SELECT COUNT(*) FROM exercises WHERE session_id = %s", ("test-session-001",))
        assert cur.fetchone()[0] == 1

        cur.execute(
            "SELECT COUNT(*) FROM working_sets WHERE exercise_id = "
            "(SELECT id FROM exercises WHERE session_id = %s)",
            ("test-session-001",),
        )
        assert cur.fetchone()[0] == 2

        cur.execute(
            "SELECT COUNT(*) FROM warmup_sets WHERE exercise_id = "
            "(SELECT id FROM exercises WHERE session_id = %s)",
            ("test-session-001",),
        )
        assert cur.fetchone()[0] == 1


def test_insert_session_correct_values(conn):
    insert_session(conn, MINIMAL_SESSION)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT date, phase, week, focus, duration_minutes, user_id, user_name "
            "FROM sessions WHERE session_id = %s",
            ("test-session-001",),
        )
        row = cur.fetchone()
    assert str(row[0]) == "2026-01-01"
    assert row[1] == 1
    assert row[2] == 1
    assert row[3] == "Push"
    assert row[4] == 60
    assert row[5] == "7"
    assert row[6] == "Apoorva Sharma"


def test_insert_session_working_set_values(conn):
    insert_session(conn, MINIMAL_SESSION)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT number, weight_kg, reps_full, reps_partial, rpe, rep_quality, failure_technique "
            "FROM working_sets WHERE exercise_id = "
            "(SELECT id FROM exercises WHERE session_id = %s) ORDER BY number",
            ("test-session-001",),
        )
        rows = cur.fetchall()

    assert rows[0][0] == 1
    assert float(rows[0][1]) == 80.0
    assert rows[0][2] == 5
    assert rows[0][3] == 0
    assert float(rows[0][4]) == 8.0
    assert rows[0][5] == "good"
    assert rows[0][6] is None

    assert rows[1][5] == "perfect"
    assert rows[1][6]["technique_type"] == "MyoReps"


def test_insert_session_is_idempotent(conn):
    insert_session(conn, MINIMAL_SESSION)
    insert_session(conn, MINIMAL_SESSION)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sessions WHERE session_id = %s", ("test-session-001",))
        assert cur.fetchone()[0] == 1


def test_insert_session_exercise_goal(conn):
    insert_session(conn, MINIMAL_SESSION)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT goal_weight_kg, goal_sets, goal_rep_min, goal_rep_max, goal_rest_min "
            "FROM exercises WHERE session_id = %s",
            ("test-session-001",),
        )
        row = cur.fetchone()

    assert float(row[0]) == 80.0
    assert row[1] == 3
    assert row[2] == 5
    assert row[3] == 6
    assert row[4] == 2


def test_insert_session_form_cues(conn):
    insert_session(conn, MINIMAL_SESSION)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT form_cues FROM exercises WHERE session_id = %s",
            ("test-session-001",),
        )
        row = cur.fetchone()

    assert row[0] == ["brace core", "retract scapula"]
