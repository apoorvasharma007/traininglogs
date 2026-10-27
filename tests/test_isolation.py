"""One person can't see or change another's data, through any endpoint. User A builds a program,
a session, a note, a custom exercise and key lifts; user B then tries every endpoint on them.
Against the real test DB."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from signed_in import TEST_DB_URL, clean_test_data, exercise_ref, USER_A, USER_B, USER_B_AUTH, auth
from traininglogs.analytics.key_lifts import DEFAULT_KEY_LIFTS
from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.insert import insert_card, insert_input

A = auth()
B = auth(USER_B_AUTH)
NO_WORKOUT = "That workout doesn't exist or was removed."
NOT_YOURS = "That exercise isn't in the library or your custom exercises."


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
    """User A's things: a custom exercise, a program whose workout plans a library exercise with
    the custom one as its alternative, a session of both, both pinned as key lifts, and a note
    read into a card."""
    squat = exercise_ref(conn, "Squat (Barbell)")
    custom = client.post("/exercises", json={"name": "Spider Curl", "primary_muscles": ["Biceps"]}, headers=A)
    assert custom.status_code == 201
    spider = {"custom_exercise_id": custom.json()["id"]}
    program = client.post("/programs", json={"name": "A's program"}, headers=A).json()
    program = client.post(f"/programs/{program['id']}/workouts", json={"name": "A1"}, headers=A).json()
    workout_id = program["workouts"][0]["id"]
    planned = client.put(f"/workouts/{workout_id}/exercises", headers=A,
                         json={"exercises": [{**squat, "working_sets": 3, "alternatives": [spider]}]})
    assert planned.status_code == 200
    client_id = uuid.uuid4().hex
    saved = client.post("/sessions", headers=A, json={
        "client_id": client_id, "date": "3002-01-05", "focus": "A1", "duration_minutes": 40,
        "program_workout_id": workout_id,
        "exercises": [{**squat, "sets": [{"weight_kg": 100, "reps": 5, "rpe": 8}]},
                      {**spider, "sets": [{"weight_kg": 12, "reps": 10}]}],
    })
    assert saved.status_code == 201
    pinned = client.put("/me/key-lifts", json={"lifts": [spider, squat]}, headers=A)
    assert [l["name"] for l in pinned.json()["key_lifts"]] == ["Spider Curl", "Squat (Barbell)"]
    raw_input_id = insert_input(conn, USER_A, "Squat 100 x 5")
    extract = {"date": "3002-01-06", "exercises": [{"number": 1, "name": "Squat", "sets": [
        {"number": 1, "weight_kg": 100.0, "rep_count": {"full": 5, "partial": 0}}]}], "uncertain_fields": []}
    extraction_id = insert_card(conn, USER_A, raw_input_id, "m", "v1", extract)
    mine = client.get("/exercises", headers=A).json()["mine"]
    return {
        "program_id": program["id"], "workout_id": workout_id, "client_id": client_id,
        "session_id": saved.json()["session_id"], "extraction_id": extraction_id,
        "program": client.get(f"/programs/{program['id']}", headers=A).json(),
        "squat_id": squat["library_exercise_id"], "custom_exercise_id": spider["custom_exercise_id"], "mine": mine,
    }


def test_lists_show_only_your_own(client, a) -> None:
    assert client.get("/sessions", headers=B).json() == []
    assert client.get("/programs", headers=B).json() == []
    both = {"library_exercise_id": a["squat_id"], "custom_exercise_id": a["custom_exercise_id"]}
    assert client.get("/exercises/last", params=both, headers=B).json() == []
    lifts = client.get("/progress/lifts", headers=B).json()
    assert [(l["name"], l["sessions"]) for l in lifts["key_lifts"]] == [(name, 0) for name in DEFAULT_KEY_LIFTS]
    assert lifts["other_lifts"] == []
    squat = client.get("/progress/lift", params={"library_exercise_id": a["squat_id"]}, headers=B).json()
    assert (squat["sessions"], squat["points"]) == (0, [])
    assert client.get("/progress/lift", params={"custom_exercise_id": a["custom_exercise_id"]}, headers=B).status_code == 404
    assert client.get("/exercises", headers=B).json()["mine"] == []
    # A still sees theirs.
    assert len(client.get("/sessions", headers=A).json()) == 1
    assert sorted(e["name"] for e in client.get("/exercises/last", params=both, headers=A).json()) == [
        "Spider Curl", "Squat (Barbell)"]
    spider = client.get("/progress/lift", params={"custom_exercise_id": a["custom_exercise_id"]}, headers=A).json()
    assert (spider["name"], len(spider["points"])) == ("Spider Curl", 1)


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
    ("PUT", "/workouts/{workout_id}/exercises", {"exercises": [{"library_exercise_id": "{squat_id}"}]}),
    ("PUT", "/workouts/{workout_id}/movements", {"warmup": [{"name": "Jog"}], "cooldown": []}),
    ("DELETE", "/workouts/{workout_id}", None),
    ("PUT", "/exercises/{custom_exercise_id}", {"name": "B was here", "primary_muscles": ["Biceps"]}),
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
    assert client.get("/exercises", headers=A).json()["mine"] == a["mine"]
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM input_text WHERE user_id = %s", (USER_B,))
        assert cur.fetchone()[0] == 0, "nothing is created for B either"


def test_someone_elses_workout_cant_be_named_in_a_session(client, conn, a) -> None:
    r = client.post("/sessions", headers=B, json={
        "client_id": uuid.uuid4().hex, "date": "3002-01-07", "duration_minutes": 10,
        "program_workout_id": a["workout_id"],
        "exercises": [{"library_exercise_id": a["squat_id"], "sets": [{"weight_kg": 10, "reps": 8}]}],
    })
    assert (r.status_code, r.json()["detail"]) == (422, NO_WORKOUT)
    raw = insert_input(conn, USER_B, "Curl 10 x 8")
    mine = insert_card(conn, USER_B, raw, "m", "v1", {"date": "3002-01-07", "exercises": [{"number": 1, "name": "Curl",
        "sets": [{"number": 1, "weight_kg": 10.0, "rep_count": {"full": 8, "partial": 0}}]}], "uncertain_fields": []})
    r = client.post(f"/extractions/{mine}/confirm", json={"program_workout_id": a["workout_id"]}, headers=B)
    assert (r.status_code, r.json()["detail"]) == (422, NO_WORKOUT)
    assert client.get("/sessions", headers=B).json() == []


def test_someone_elses_custom_exercise_cant_be_named_in_a_session_or_plan(client, conn, a) -> None:
    """Naming A's custom exercise is refused as an unknown exercise, and nothing is saved, even
    beside an exercise B may use."""
    theirs = {"custom_exercise_id": a["custom_exercise_id"]}
    squat = {"library_exercise_id": a["squat_id"]}
    for exercises in ([theirs], [squat, theirs]):
        r = client.post("/sessions", headers=B, json={
            "client_id": uuid.uuid4().hex, "date": "3002-01-07", "duration_minutes": 10,
            "exercises": [{**e, "sets": [{"weight_kg": 10, "reps": 8}]} for e in exercises],
        })
        assert (r.status_code, r.json()["detail"]) == (422, NOT_YOURS), exercises
    assert client.get("/sessions", headers=B).json() == []
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM input_text WHERE user_id = %s", (USER_B,))
        assert cur.fetchone()[0] == 0

    program = client.post("/programs", json={"name": "B's program"}, headers=B).json()
    program = client.post(f"/programs/{program['id']}/workouts", json={"name": "B1"}, headers=B).json()
    workout_id = program["workouts"][0]["id"]
    for plan in ([theirs], [{**squat, "alternatives": [theirs]}]):
        r = client.put(f"/workouts/{workout_id}/exercises", json={"exercises": plan}, headers=B)
        assert (r.status_code, r.json()["detail"]) == (422, NOT_YOURS), plan
    assert client.get(f"/programs/{program['id']}", headers=B).json()["workouts"][0]["exercises"] == []
    assert client.get("/exercises", headers=A).json()["mine"] == a["mine"]


def test_someone_elses_custom_exercise_cant_be_a_key_lift(client, a) -> None:
    """B can't pin A's custom exercise: refused, B keeps the defaults, and A's pins stay A's."""
    r = client.put("/me/key-lifts", json={"lifts": [{"custom_exercise_id": a["custom_exercise_id"]}]}, headers=B)
    assert (r.status_code, r.json()["detail"]) == (422, NOT_YOURS)
    lifts = client.get("/progress/lifts", headers=B).json()
    assert [(l["name"], l["sessions"]) for l in lifts["key_lifts"]] == [(name, 0) for name in DEFAULT_KEY_LIFTS]
    mine = client.get("/progress/lifts", headers=A).json()["key_lifts"]
    assert [(l["name"], l["sessions"]) for l in mine] == [("Spider Curl", 1), ("Squat (Barbell)", 1)]


def test_someone_elses_linked_custom_exercise_finds_nothing_of_yours(client, a) -> None:
    """A's custom exercise linked to Squat (Barbell), asked about by B, who has squatted: B gets
    nothing, not B's own squats under A's id, which would show B what A linked."""
    linked = client.post("/exercises", headers=A, json={
        "name": "Low-bar Squat", "linked_library_exercise_id": a["squat_id"],
    }).json()
    r = client.post("/sessions", headers=B, json={
        "client_id": uuid.uuid4().hex, "date": "3002-01-08", "duration_minutes": 10,
        "exercises": [{"library_exercise_id": a["squat_id"], "sets": [{"weight_kg": 60, "reps": 5}]}],
    })
    assert r.status_code == 201
    asked = client.get("/exercises/last", params={"custom_exercise_id": linked["id"]}, headers=B)
    assert (asked.status_code, asked.json()) == (200, [])
    mine = client.get("/exercises/last", params={"library_exercise_id": a["squat_id"]}, headers=B).json()
    assert [(e["name"], e["sets"][0]["weight_kg"]) for e in mine] == [("Squat (Barbell)", 60)]


def test_a_phone_id_someone_else_used_is_just_a_new_session(client, a) -> None:
    """Phone ids are unique per person: B sending A's id gets B's own new session, and nothing of
    A's is touched or revealed."""
    r = client.post("/sessions", headers=B, json={
        "client_id": a["client_id"], "date": "3002-01-07", "duration_minutes": 10,
        "exercises": [{"library_exercise_id": a["squat_id"], "sets": [{"weight_kg": 10, "reps": 8}]}],
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
        if "{" in route.path and not route.path.startswith("/templates")
    }
    assert named <= {(m, p) for m, p, _ in ATTEMPTS}, named - {(m, p) for m, p, _ in ATTEMPTS}
    assert covered
