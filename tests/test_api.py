import os
import pytest
from fastapi.testclient import TestClient

from traininglogs.api.app import app
from traininglogs.db.db import get_connection, apply_schema
from traininglogs.db.insert_v2 import insert_session
from traininglogs.models.models_v2 import TrainingSession

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["API_KEY"] = "testkey"

SESSION_A = {
    "data_model_version": "0.0.1",
    "data_model_type": "TrainingSession",
    "session_id": "api-test-session-001",
    "user_id": "7",
    "user_name": "Apoorva Sharma",
    "date": "2026-02-01",
    "program": "Test Program",
    "program_author": "Test Author",
    "program_length_weeks": 12,
    "phase": 1,
    "week": 2,
    "is_deload_week": False,
    "focus": "Push Hypertrophy",
    "session_duration_minutes": 75,
    "exercises": [
        {
            "number": 1,
            "name": "Bench Press",
            "notes": None,
            "warmup_notes": None,
            "form_cues": ["brace core"],
            "target_muscle_groups": None,
            "rep_tempo": None,
            "current_goal": {
                "weight_kg": 80.0,
                "sets": 3,
                "rep_range": {"min": 5, "max": 6},
                "rest_minutes": 3,
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
            ],
        }
    ],
}

SESSION_B = {
    **SESSION_A,
    "session_id": "api-test-session-002",
    "date": "2026-03-01",
    "phase": 2,
    "week": 1,
    "focus": "Pull Hypertrophy",
}


@pytest.fixture(scope="module")
def db_conn():
    conn = get_connection(TEST_DB_URL)
    apply_schema(conn)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def client(db_conn):
    insert_session(db_conn, TrainingSession.model_validate(SESSION_A))
    insert_session(db_conn, TrainingSession.model_validate(SESSION_B))
    with TestClient(app) as c:
        yield c
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE session_id LIKE 'api-test-%'")
    db_conn.commit()


def test_list_sessions_returns_all(client):
    r = client.get("/sessions", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    ids = [s["session_id"] for s in r.json()]
    assert "api-test-session-001" in ids
    assert "api-test-session-002" in ids


def test_list_sessions_filter_by_phase(client):
    r = client.get("/sessions?phase=1", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    results = r.json()
    assert all(s["phase"] == 1 for s in results)
    ids = [s["session_id"] for s in results]
    assert "api-test-session-001" in ids
    assert "api-test-session-002" not in ids


def test_list_sessions_filter_by_phase_and_week(client):
    r = client.get("/sessions?phase=2&week=1", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    results = [s for s in r.json() if s["session_id"].startswith("api-test-")]
    assert len(results) == 1
    assert results[0]["session_id"] == "api-test-session-002"


def test_list_sessions_filter_by_date_range(client):
    r = client.get(
        "/sessions?from_date=2026-02-01&to_date=2026-02-28",
        headers={"x-api-key": "testkey"},
    )
    assert r.status_code == 200
    test_results = [s for s in r.json() if s["session_id"].startswith("api-test-")]
    assert len(test_results) == 1
    assert test_results[0]["session_id"] == "api-test-session-001"


def test_session_detail_returns_full_structure(client):
    r = client.get("/sessions/api-test-session-001", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "api-test-session-001"
    assert body["focus"] == "Push Hypertrophy"
    assert len(body["exercises"]) == 1
    exercise = body["exercises"][0]
    assert exercise["name"] == "Bench Press"
    assert len(exercise["working_sets"]) == 1
    assert len(exercise["warmup_sets"]) == 1


def test_session_detail_not_found(client):
    r = client.get("/sessions/does-not-exist", headers={"x-api-key": "testkey"})
    assert r.status_code == 404


def test_exercise_history_returns_sets_in_order(client):
    r = client.get("/exercises/Bench Press/history", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    rows = [row for row in r.json() if row["session_id"].startswith("api-test-")]
    assert len(rows) == 2
    dates = [row["date"] for row in rows]
    assert dates == sorted(dates)


def test_exercise_history_case_insensitive(client):
    r = client.get("/exercises/bench press/history", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    rows = [row for row in r.json() if row["session_id"].startswith("api-test-")]
    assert len(rows) == 2


def test_exercise_history_not_found(client):
    r = client.get("/exercises/Squat/history", headers={"x-api-key": "testkey"})
    assert r.status_code == 404


def test_auth_rejects_wrong_key(client):
    r = client.get("/sessions", headers={"x-api-key": "wrongkey"})
    assert r.status_code == 401


def test_auth_rejects_missing_key(client):
    r = client.get("/sessions")
    assert r.status_code == 401
