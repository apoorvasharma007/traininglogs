import os
import pytest

from traininglogs.db.db import get_connection, apply_schema
from traininglogs.db.insert import insert_session
from traininglogs.analytics.queries import (
    exercise_progression,
    personal_records,
    volume_by_session,
    rpe_trend,
    top_rpe_sets,
    sessions_per_week,
    failure_technique_usage,
    custom_query,
)

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)

# Two sessions: same exercise across both so we can test progression and PRs
SESSION_1 = {
    "session_id": "q-test-session-001",
    "user_id": "7",
    "user_name": "Apoorva Sharma",
    "date": "2026-01-01",
    "program": "Test",
    "program_author": "Test",
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
            "notes": None,
            "warmup_notes": None,
            "form_cues": [],
            "target_muscle_groups": None,
            "rep_tempo": None,
            "current_goal": {"weight_kg": 80.0, "sets": 3, "rep_range": {"min": 5, "max": 6}, "rest_minutes": 3},
            "warmup_sets": None,
            "working_sets": [
                {"number": 1, "weight_kg": 80.0, "rep_count": {"full": 5, "partial": 0}, "rpe": 8.0, "rep_quality_assessment": "good", "actual_rest_minutes": None, "notes": None, "failure_technique": None},
                {"number": 2, "weight_kg": 80.0, "rep_count": {"full": 5, "partial": 0}, "rpe": 9.0, "rep_quality_assessment": "good", "actual_rest_minutes": None, "notes": None, "failure_technique": {"technique_type": "MyoReps", "details": {"mini_sets": [{"number": 1, "rep_count": {"full": 3, "partial": 0}}]}}},
            ],
        }
    ],
}

SESSION_2 = {
    "session_id": "q-test-session-002",
    "user_id": "7",
    "user_name": "Apoorva Sharma",
    "date": "2026-01-08",
    "program": "Test",
    "program_author": "Test",
    "program_length_weeks": 12,
    "phase": 1,
    "week": 2,
    "is_deload_week": False,
    "focus": "Push",
    "session_duration_minutes": 65,
    "exercises": [
        {
            "number": 1,
            "name": "Bench Press",
            "notes": None,
            "warmup_notes": None,
            "form_cues": [],
            "target_muscle_groups": None,
            "rep_tempo": None,
            "current_goal": {"weight_kg": 82.5, "sets": 3, "rep_range": {"min": 5, "max": 6}, "rest_minutes": 3},
            "warmup_sets": None,
            "working_sets": [
                {"number": 1, "weight_kg": 82.5, "rep_count": {"full": 5, "partial": 0}, "rpe": 10.0, "rep_quality_assessment": "perfect", "actual_rest_minutes": None, "notes": None, "failure_technique": None},
                {"number": 2, "weight_kg": 82.5, "rep_count": {"full": 4, "partial": 1}, "rpe": 10.0, "rep_quality_assessment": None, "actual_rest_minutes": None, "notes": None, "failure_technique": {"technique_type": "LLP", "details": {"partial_rep_count": 4}}},
            ],
        }
    ],
}


@pytest.fixture(scope="module")
def conn():
    c = get_connection(TEST_DB_URL)
    apply_schema(c)
    insert_session(c, SESSION_1)
    insert_session(c, SESSION_2)
    yield c
    with c.cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE session_id LIKE 'q-test-%'")
    c.commit()
    c.close()


def test_exercise_progression_returns_sets_in_order(conn):
    rows = exercise_progression(conn, "Bench Press")
    test_rows = [r for r in rows if r["set_number"] and str(r.get("date")) >= "2026-01-01"]
    dates = [str(r["date"]) for r in test_rows]
    assert dates == sorted(dates)


def test_exercise_progression_case_insensitive(conn):
    rows_lower = exercise_progression(conn, "bench press")
    rows_upper = exercise_progression(conn, "Bench Press")
    assert len(rows_lower) == len(rows_upper)


def test_exercise_progression_unknown_exercise(conn):
    rows = exercise_progression(conn, "Deadlift")
    assert rows == []


def test_personal_records_picks_heaviest(conn):
    rows = personal_records(conn)
    bench = next((r for r in rows if r["exercise"] == "Bench Press"), None)
    assert bench is not None
    assert float(bench["weight_kg"]) == 82.5


def test_volume_by_session_counts_working_sets(conn):
    rows = volume_by_session(conn, phase=1)
    test_rows = [r for r in rows if r["session_id"].startswith("q-test-")]
    assert len(test_rows) == 2
    for r in test_rows:
        assert r["total_working_sets"] == 2


def test_volume_by_session_phase_filter(conn):
    rows = volume_by_session(conn, phase=99)
    test_rows = [r for r in rows if r["session_id"].startswith("q-test-")]
    assert test_rows == []


def test_rpe_trend_averages_correctly(conn):
    rows = rpe_trend(conn, phase=1)
    s1 = next((r for r in rows if str(r["date"]) == "2026-01-01"), None)
    assert s1 is not None
    assert float(s1["avg_rpe"]) == 8.5  # (8 + 9) / 2


def test_top_rpe_sets_only_returns_rpe10(conn):
    rows = top_rpe_sets(conn, n=100)
    bench_rows = [r for r in rows if r["exercise"] == "Bench Press"]
    assert all(float(r["rpe"]) == 10.0 for r in bench_rows)


def test_sessions_per_week_counts_correctly(conn):
    rows = sessions_per_week(conn)
    phase1_week1 = next((r for r in rows if r["phase"] == 1 and r["week"] == 1), None)
    assert phase1_week1 is not None
    assert phase1_week1["session_count"] >= 1


def test_failure_technique_usage_counts(conn):
    rows = failure_technique_usage(conn)
    techniques = {r["technique"]: r["usage_count"] for r in rows}
    assert "MyoReps" in techniques
    assert "LLP" in techniques
    assert techniques["MyoReps"] >= 1
    assert techniques["LLP"] >= 1


def test_custom_query_returns_results(conn):
    rows = custom_query(
        conn,
        "SELECT session_id FROM sessions WHERE session_id LIKE %s ORDER BY date ASC",
        ["q-test-%"],
    )
    assert len(rows) == 2
    assert rows[0]["session_id"] == "q-test-session-001"
    assert rows[1]["session_id"] == "q-test-session-002"
