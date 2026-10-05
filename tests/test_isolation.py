"""One person can't see or change another's data, through any endpoint. User A builds a program,
a session and a note; user B then tries every endpoint on them. Against the real test DB."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from signed_in import TEST_DB_URL, clean_test_data, USER_A, USER_B, USER_B_AUTH, auth
from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.insert import insert_card, insert_input

A = auth()
B = auth(USER_B_AUTH)


@pytest.fixture()
def conn():
    c = get_connection(TEST_DB_URL)
    apply_schema(c)
    clean_test_data(c)
    yield c
    clean_test_data(c)
    c.close()


@pytest.fixture()
def client(conn):
    from traininglogs.api.app import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def a(client, conn) -> dict:
    """User A's things: a program with a workout, a saved session, and a note read into a card."""
    program = client.post("/programs", json={"name": "A's program"}, headers=A).json()
    program = client.post(f"/programs/{program['id']}/workouts", json={"name": "A1"}, headers=A).json()
    workout_id = program["workouts"][0]["id"]
    client.put(f"/workouts/{workout_id}/exercises", headers=A, json={"exercises": [{"name": "Squat", "working_sets": 3}]})
    client_id = uuid.uuid4().hex
    saved = client.post("/sessions", headers=A, json={
        "client_id": client_id, "date": "3002-01-05", "focus": "A1", "duration_minutes": 40,
        "program_workout_id": workout_id,
        "exercises": [{"name": "Squat", "sets": [{"weight_kg": 100, "reps": 5, "rpe": 8}]}],
    })
    assert saved.status_code == 201
    raw_input_id = insert_input(conn, USER_A, "Squat 100 x 5")
    extract = {"date": "3002-01-06", "exercises": [{"number": 1, "name": "Squat", "sets": [
        {"number": 1, "weight_kg": 100.0, "rep_count": {"full": 5, "partial": 0}}]}], "uncertain_fields": []}
    extraction_id = insert_card(conn, USER_A, raw_input_id, "m", "v1", extract)
    return {
        "program_id": program["id"], "workout_id": workout_id, "client_id": client_id,
        "session_id": saved.json()["session_id"], "extraction_id": extraction_id,
        "program": client.get(f"/programs/{program['id']}", headers=A).json(),
    }


def test_lists_show_only_your_own(client, a) -> None:
    assert client.get("/sessions", headers=B).json() == []
    assert client.get("/programs", headers=B).json() == []
    assert client.get("/exercises/last", params={"name": "Squat"}, headers=B).json() == []
    lifts = client.get("/progress/lifts", headers=B).json()
    assert all(l["sessions"] == 0 for l in lifts["key_lifts"]) and lifts["other_lifts"] == []
    assert client.get("/progress/lifts/Squat", headers=B).json()["points"] == []
    assert client.get("/exercises/Squat/history", headers=B).status_code == 404
    # A still sees theirs.
    assert len(client.get("/sessions", headers=A).json()) == 1


# Every endpoint that names one of A's things, called by B. (method, path, json body)
ATTEMPTS = [
    ("GET", "/sessions/{session_id}", None),
    ("GET", "/extractions/{extraction_id}", None),
    ("POST", "/extractions/{extraction_id}/confirm", {}),
    ("POST", "/extractions/{extraction_id}/correct", {"instruction": "make it 200 kg"}),
    ("POST", "/extractions/{extraction_id}/edit", {"edits": [{"path": "exercises.0.sets.0", "field": "weight_kg", "value": 1}]}),
    ("GET", "/programs/{program_id}", None),
    ("PATCH", "/programs/{program_id}", {"name": "B was here"}),
    ("POST", "/programs/{program_id}/follow", None),
    ("POST", "/programs/{program_id}/unfollow", None),
    ("DELETE", "/programs/{program_id}", None),
    ("POST", "/programs/{program_id}/workouts", {"name": "B's"}),
    ("PUT", "/programs/{program_id}/workout-order", {"workout_ids": ["{workout_id}"]}),
    ("PATCH", "/workouts/{workout_id}", {"name": "B was here"}),
    ("PUT", "/workouts/{workout_id}/exercises", {"exercises": [{"name": "Curl"}]}),
    ("PUT", "/workouts/{workout_id}/movements", {"warmup": [{"name": "Jog"}], "cooldown": []}),
    ("DELETE", "/workouts/{workout_id}", None),
]


def _fill(value, ids: dict):
    if isinstance(value, str):
        return value.format(**ids)
    if isinstance(value, list):
        return [_fill(v, ids) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    return value


@pytest.mark.parametrize(("method", "path", "body"), ATTEMPTS, ids=[f"{m} {p}" for m, p, _ in ATTEMPTS])
def test_someone_elses_things_are_not_found_and_unchanged(client, conn, a, method, path, body) -> None:
    r = client.request(method, _fill(path, a), json=_fill(body, a), headers=B)
    assert r.status_code == 404, r.text
    assert client.get(f"/programs/{a['program_id']}", headers=A).json() == a["program"]
    assert client.get(f"/extractions/{a['extraction_id']}", headers=A).status_code == 200
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM input_text WHERE user_id = %s", (USER_B,))
        assert cur.fetchone()[0] == 0, "nothing is created for B either"


def test_someone_elses_workout_cant_be_named_in_a_session(client, conn, a) -> None:
    r = client.post("/sessions", headers=B, json={
        "client_id": uuid.uuid4().hex, "date": "3002-01-07", "duration_minutes": 10,
        "program_workout_id": a["workout_id"], "exercises": [{"name": "Curl", "sets": [{"weight_kg": 10, "reps": 8}]}],
    })
    assert r.status_code == 422
    raw = insert_input(conn, USER_B, "Curl 10 x 8")
    mine = insert_card(conn, USER_B, raw, "m", "v1", {"date": "3002-01-07", "exercises": [{"number": 1, "name": "Curl",
        "sets": [{"number": 1, "weight_kg": 10.0, "rep_count": {"full": 8, "partial": 0}}]}], "uncertain_fields": []})
    r = client.post(f"/extractions/{mine}/confirm", json={"program_workout_id": a["workout_id"]}, headers=B)
    assert r.status_code == 422
    assert client.get("/sessions", headers=B).json() == []


def test_a_phone_id_someone_else_used_is_just_a_new_session(client, a) -> None:
    """Phone ids are unique per person: B sending A's id gets B's own new session, and nothing of
    A's is touched or revealed."""
    r = client.post("/sessions", headers=B, json={
        "client_id": a["client_id"], "date": "3002-01-07", "duration_minutes": 10,
        "exercises": [{"name": "Curl", "sets": [{"weight_kg": 10, "reps": 8}]}],
    })
    assert r.status_code == 201 and r.json()["session_id"] != a["session_id"]
    assert [s["session_id"] for s in client.get("/sessions", headers=A).json()] == [a["session_id"]]


def test_following_is_per_person(client, a) -> None:
    client.post(f"/programs/{a['program_id']}/follow", headers=A)
    mine = client.post("/programs", json={"name": "B's program"}, headers=B).json()
    client.post(f"/programs/{mine['id']}/follow", headers=B)
    assert client.get(f"/programs/{a['program_id']}", headers=A).json()["following"] is True
    assert client.get(f"/programs/{mine['id']}", headers=B).json()["following"] is True


def test_every_endpoint_that_names_a_thing_is_covered_here() -> None:
    """A new endpoint taking an id must be added to ATTEMPTS, so it gets this test too."""
    from traininglogs.api.app import app

    covered = {(m, p.split("{")[0] + "{" + p.split("{")[1]) for m, p, _ in ATTEMPTS}
    named = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set()) - {"HEAD"}
        if "{" in route.path and not route.path.startswith(("/templates", "/progress", "/exercises"))
    }
    assert named <= {(m, p) for m, p, _ in ATTEMPTS}, named - {(m, p) for m, p, _ in ATTEMPTS}
    assert covered
