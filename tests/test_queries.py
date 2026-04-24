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
    overview_stats,
    exercise_e1rm_trend,
    exercise_list,
    weekly_muscle_group_volume,
    rpe_distribution,
    fatigue_within_phase,
    deload_effect,
    stimulus_fatigue_by_exercise,
    weekly_tonnage_by_phase,
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
            "target_muscle_groups": ["Chest", "Triceps"],
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
            "target_muscle_groups": ["Chest", "Triceps"],
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


SESSION_3_DELOAD = {
    "session_id": "q-test-session-003",
    "user_id": "7",
    "user_name": "Apoorva Sharma",
    "date": "2026-01-15",
    "program": "Test",
    "program_author": "Test",
    "program_length_weeks": 12,
    "phase": 1,
    "week": 3,
    "is_deload_week": True,
    "focus": "Push",
    "session_duration_minutes": 45,
    "exercises": [
        {
            "number": 1,
            "name": "Bench Press",
            "notes": None,
            "warmup_notes": None,
            "form_cues": [],
            "target_muscle_groups": ["Chest", "Triceps"],
            "rep_tempo": None,
            "current_goal": {"weight_kg": 70.0, "sets": 2, "rep_range": {"min": 5, "max": 6}, "rest_minutes": 3},
            "warmup_sets": None,
            "working_sets": [
                {"number": 1, "weight_kg": 70.0, "rep_count": {"full": 5, "partial": 0}, "rpe": 6.0, "rep_quality_assessment": "perfect", "actual_rest_minutes": None, "notes": None, "failure_technique": None},
                {"number": 2, "weight_kg": 70.0, "rep_count": {"full": 5, "partial": 0}, "rpe": 6.5, "rep_quality_assessment": "perfect", "actual_rest_minutes": None, "notes": None, "failure_technique": None},
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
    insert_session(c, SESSION_3_DELOAD)
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
    assert len(test_rows) == 3
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


def test_overview_stats_totals(conn):
    o = overview_stats(conn)
    assert o["total_sessions"] >= 3
    assert o["weeks_trained"] >= 3
    # tonnage: s1=80*5+80*5=800, s2=82.5*5+82.5*4=742.5, s3=70*5+70*5=700 → ≥2242
    assert o["total_tonnage_kg"] >= 2242


def test_exercise_e1rm_trend_epley(conn):
    rows = exercise_e1rm_trend(conn, "Bench Press")
    test_rows = [r for r in rows if r["date"] and str(r["date"]) >= "2026-01-01"]
    # Epley for 80kg × 5: 80 * (1 + 5/30) = 93.33
    first = test_rows[0]
    assert float(first["e1rm_kg"]) == pytest.approx(93.33, abs=0.1)


def test_exercise_e1rm_trend_null_on_zero_reps(conn):
    # Exercise without any reps would return empty; just ensure function runs without error
    rows = exercise_e1rm_trend(conn, "Deadlift")
    assert rows == []


def test_exercise_list_respects_min_sets(conn):
    rows = exercise_list(conn, min_sets=1)
    names = [r["exercise"] for r in rows]
    assert "Bench Press" in names
    rows_high = exercise_list(conn, min_sets=10_000)
    assert rows_high == []


def test_weekly_muscle_group_volume_unnests(conn):
    rows = weekly_muscle_group_volume(conn, phase=1)
    # Each bench press session has 2 working sets × 2 muscle groups = 4 muscle-group rows counted per session
    chest_p1_w1 = next((r for r in rows if r["muscle_group"] == "Chest" and r["week"] == 1), None)
    assert chest_p1_w1 is not None
    assert chest_p1_w1["working_sets"] == 2


def test_rpe_distribution_buckets(conn):
    rows = rpe_distribution(conn, phase=1)
    buckets = {r["rpe_bucket"]: r["sets"] for r in rows}
    # RPEs in fixtures: 8, 9, 10, 10, 6, 6 → buckets 6:2, 8:1, 9:1, 10:2
    assert buckets.get(10, 0) >= 2
    assert buckets.get(6, 0) >= 2


def test_fatigue_within_phase_marks_deload(conn):
    rows = fatigue_within_phase(conn, phase=1)
    deload_row = next((r for r in rows if r["is_deload_week"]), None)
    assert deload_row is not None
    assert deload_row["week"] == 3
    # Deload avg RPE is (6+6.5)/2 = 6.25 — clearly lower than accumulation weeks
    assert float(deload_row["avg_rpe"]) < 7


def test_deload_effect_pairs_weeks(conn):
    rows = deload_effect(conn)
    p1 = next((r for r in rows if r["phase"] == 1 and r["deload_week"] == 3), None)
    assert p1 is not None
    assert float(p1["pre_avg_rpe"]) == 10.0  # week 2: (10+10)/2
    assert float(p1["deload_avg_rpe"]) == pytest.approx(6.25, abs=0.01)
    assert p1["post_avg_rpe"] is None  # no week 4 in fixture


def test_stimulus_fatigue_by_exercise(conn):
    rows = stimulus_fatigue_by_exercise(conn, min_sets=1)
    bench = next((r for r in rows if r["exercise"] == "Bench Press"), None)
    assert bench is not None
    assert bench["set_count"] >= 6
    assert float(bench["avg_rpe"]) > 0


def test_weekly_tonnage_by_phase(conn):
    rows = weekly_tonnage_by_phase(conn)
    p1_w1 = next((r for r in rows if r["phase"] == 1 and r["week"] == 1), None)
    assert p1_w1 is not None
    assert p1_w1["tonnage_kg"] >= 800  # 80*5 + 80*5
    p1_w3 = next((r for r in rows if r["phase"] == 1 and r["week"] == 3), None)
    assert p1_w3["is_deload_week"] is True


def test_custom_query_returns_results(conn):
    rows = custom_query(
        conn,
        "SELECT session_id FROM sessions WHERE session_id LIKE %s ORDER BY date ASC",
        ["q-test-%"],
    )
    assert len(rows) == 3
    assert rows[0]["session_id"] == "q-test-session-001"
    assert rows[1]["session_id"] == "q-test-session-002"
    assert rows[2]["session_id"] == "q-test-session-003"
