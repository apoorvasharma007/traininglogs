"""GET /progress/lifts and /progress/lifts/{name} against the real test DB."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.insert import insert_session
from traininglogs.models.models import TrainingSession

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["API_KEY"] = "testkey"
HEADERS = {"x-api-key": "testkey"}

IDS = ["progress-test-001", "progress-test-002"]


def session(sid: str, day: str, weight: float) -> TrainingSession:
    return TrainingSession.model_validate({
        "data_model_version": "0.0.1", "data_model_type": "TrainingSession",
        "session_id": sid, "user_id": "7", "user_name": "Apoorva Sharma", "date": day,
        "focus": "Strength",
        "exercises": [{
            "number": 1, "name": "Squats",
            "current_goal": {"weight_kg": 140.0},
            "sets": [{"number": 1, "weight_kg": weight, "rep_count": {"full": 3, "partial": 0},
                      "rpe": 9.0}],
        }],
    })


@pytest.fixture(scope="module")
def client():
    conn = get_connection(TEST_DB_URL)
    apply_schema(conn)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE session_id = ANY(%s)", (IDS,))
    conn.commit()
    insert_session(conn, session(IDS[0], "3000-01-01", 120.0))
    insert_session(conn, session(IDS[1], "3000-01-08", 125.0))
    from traininglogs.api.app import app

    with TestClient(app) as c:
        yield c
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE session_id = ANY(%s)", (IDS,))
    conn.commit()
    conn.close()


def test_lifts_lists_key_lifts_with_squat_found_under_its_variant(client) -> None:
    r = client.get("/progress/lifts", headers=HEADERS)
    assert r.status_code == 200
    squat = next(k for k in r.json()["key_lifts"] if k["name"] == "Squat")
    assert squat["sessions"] >= 2 and squat["best"] >= 141.7


def test_lift_detail_points_records_and_goal(client) -> None:
    r = client.get("/progress/lifts/Squat", headers=HEADERS)
    assert r.status_code == 200
    mine = [p for p in r.json()["points"] if p["session_id"] in IDS]
    assert [(p["value"], p["method"], p["goal_weight_kg"]) for p in mine] == [
        (136.0, "rpe", 140.0), (141.7, "rpe", 140.0),
    ]
    assert mine[1]["best_set"] == {"number": 1, "weight_kg": 125.0, "reps": 3, "rpe": 9.0}


def test_unknown_lift_is_404(client) -> None:
    assert client.get("/progress/lifts/Nordic%20curl", headers=HEADERS).status_code == 404


def test_requires_auth(client) -> None:
    assert client.get("/progress/lifts").status_code == 401
