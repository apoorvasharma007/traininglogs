"""GET /progress/lifts and /progress/lifts/{name} against the real test DB."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from traininglogs.db.db import apply_schema, get_connection
from signed_in import USER_A, USER_B_AUTH, auth, clean_test_data, save_session

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL
HEADERS = auth()

def session(day: str, weight: float) -> dict:
    return {
        "date": day,
        "focus": "Strength",
        "exercises": [{
            "number": 1, "name": "Squats",
            "current_goal": {"weight_kg": 140.0},
            "sets": [{"number": 1, "weight_kg": weight, "rep_count": {"full": 3, "partial": 0},
                      "rpe": 9.0}],
        }],
    }


@pytest.fixture(scope="module")
def client():
    conn = get_connection(TEST_DB_URL)
    apply_schema(conn)
    clean_test_data(conn)
    save_session(conn, session("3000-01-01", 120.0))
    save_session(conn, session("3000-01-08", 125.0))
    from traininglogs.api.app import app

    with TestClient(app) as c:
        yield c
    clean_test_data(conn)
    conn.close()


def test_lifts_lists_key_lifts_with_squat_found_under_its_variant(client) -> None:
    r = client.get("/progress/lifts", headers=HEADERS)
    assert r.status_code == 200
    squat = next(k for k in r.json()["key_lifts"] if k["name"] == "Squat")
    assert squat["sessions"] >= 2 and squat["best"] >= 141.7


def test_lift_detail_points_records_and_goal(client) -> None:
    r = client.get("/progress/lifts/Squat", headers=HEADERS)
    assert r.status_code == 200
    mine = r.json()["points"]
    assert [(p["value"], p["method"], p["goal_weight_kg"]) for p in mine] == [
        (136.0, "rpe", 140.0), (141.7, "rpe", 140.0),
    ]
    assert mine[1]["best_set"] == {"number": 1, "weight_kg": 125.0, "reps": 3, "rpe": 9.0}


def test_unknown_lift_is_404(client) -> None:
    assert client.get("/progress/lifts/Nordic%20curl", headers=HEADERS).status_code == 404


def test_requires_auth(client) -> None:
    assert client.get("/progress/lifts").status_code == 401


def test_ai_usage_is_the_persons_own_total(client) -> None:
    from signed_in import USER_B
    from traininglogs.db.insert import insert_ai_calls, insert_input

    call = {"step": "extract_exercise", "model": "m", "attempts": 1, "ms": 10}
    conn = get_connection(TEST_DB_URL)
    assert client.get("/me/ai-usage", headers=auth()).json() == {"total_usd": 0.0}
    insert_ai_calls(conn, USER_A, insert_input(conn, USER_A, "note 1"), [{**call, "cost_usd": 0.0185}, {**call, "cost_usd": 0.002}])
    insert_ai_calls(conn, USER_B, insert_input(conn, USER_B, "note 2"), [{**call, "cost_usd": 0.5}])
    conn.close()
    assert client.get("/me/ai-usage", headers=auth()).json() == {"total_usd": 0.0205}
    assert client.get("/me/ai-usage", headers=auth(USER_B_AUTH)).json() == {"total_usd": 0.5}
