"""GET /me/export: everything a person logged, as a CSV of sets or as JSON."""
from __future__ import annotations

import csv
import io
import os

import pytest
from fastapi.testclient import TestClient

from traininglogs.db.db import apply_schema, get_connection
from signed_in import USER_B_AUTH, auth, clean_test_data, save_session

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL
HEADERS = auth()

SESSION = {
    "date": "3000-01-01",
    "focus": "Strength",
    "exercises": [{
        "number": 1, "name": "Squat", "notes": "felt good",
        "warmup_sets": [{"number": 1, "weight_kg": 60.0, "rep_count": 5}],
        "sets": [
            {"number": 1, "weight_kg": 100.0, "rep_count": {"full": 5, "partial": 0}, "rpe": 8.0},
            {"number": 2, "weight_kg": 102.5, "rep_count": {"full": 4, "partial": 0}},
        ],
    }],
}


@pytest.fixture(scope="module")
def client():
    conn = get_connection(TEST_DB_URL)
    apply_schema(conn)
    clean_test_data(conn)
    save_session(conn, SESSION)
    from traininglogs.api.app import app

    with TestClient(app) as c:
        yield c
    clean_test_data(conn)
    conn.close()


def test_csv_has_one_line_per_set_warm_ups_first(client) -> None:
    r = client.get("/me/export?format=csv", headers=HEADERS)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'filename="traininglogs-' in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert [(x["exercise"], x["set_kind"], x["weight_kg"], x["reps"], x["rpe"]) for x in rows] == [
        ("Squat", "warmup", "60.0", "5", ""),
        ("Squat", "working", "100.0", "5", "8.0"),
        ("Squat", "working", "102.5", "4", ""),
    ]
    assert rows[0]["date"] == "3000-01-01" and rows[0]["session"] == "Strength" and rows[0]["exercise_notes"] == "felt good"


def test_json_nests_sets_in_exercises_in_sessions(client) -> None:
    r = client.get("/me/export?format=json", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"exported_at", "app_version", "sessions", "programs"}
    [session] = body["sessions"]
    assert (session["date"], session["name"]) == ("3000-01-01", "Strength")
    [squat] = session["exercises"]
    assert [(x["kind"], x["weight_kg"], x["reps"]) for x in squat["sets"]] == [
        ("warmup", 60.0, 5), ("working", 100.0, 5), ("working", 102.5, 4),
    ]


def test_only_your_own_data(client) -> None:
    rows = list(csv.DictReader(io.StringIO(client.get("/me/export", headers=auth(sub=USER_B_AUTH)).text)))
    assert rows == []


def test_requires_sign_in(client) -> None:
    assert client.get("/me/export").status_code == 401
