"""GET /progress/lifts, GET /progress/lift and PUT /me/key-lifts against the real test DB."""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.ids import new_id
from signed_in import USER_A, USER_B, USER_B_AUTH, auth, clean_test_data, exercise_ref, save_session

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL
HEADERS = auth()

# The lifts Progress shows first to someone who hasn't pinned any, in this order: a promise to
# every new person, so it's written out here rather than read from DEFAULT_KEY_LIFTS.
DEFAULTS = [
    "Squat (Barbell)", "Bench Press (Barbell)", "Overhead Press (Barbell)", "Deadlift (Barbell)",
    "Clean (Barbell)", "Pull-up (Bodyweight)",
]
REFS: dict[str, dict] = {}


def session(day: str, ref: dict, sets: list[dict], goal_kg: float | None = None) -> dict:
    return {
        "date": day,
        "focus": "Strength",
        "exercises": [{
            "number": 1, "name": "-", **ref,
            "current_goal": {"weight_kg": goal_kg} if goal_kg else None,
            "sets": [{"number": n, **s} for n, s in enumerate(sets, start=1)],
        }],
    }


def heavy(weight: float) -> dict:
    return {"weight_kg": weight, "rep_count": {"full": 3, "partial": 0}, "rpe": 9.0}


def bodyweight(reps: int) -> dict:
    return {"rep_count": {"full": reps, "partial": 0}}


def _no_pins(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET key_lifts = NULL WHERE id IN (%s, %s)", (USER_A, USER_B))
    conn.commit()


@pytest.fixture(scope="module")
def conn():
    connection = get_connection(TEST_DB_URL)
    apply_schema(connection)
    clean_test_data(connection)
    REFS.update({name: exercise_ref(connection, name) for name in DEFAULTS})
    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO custom_exercises (id, user_id, name, linked_library_exercise_id) VALUES (%s, %s, %s, %s)"
            " RETURNING id::text",
            (new_id(), USER_A, "Low-bar Squat", REFS["Squat (Barbell)"]["library_exercise_id"]),
        )
        REFS["Low-bar Squat"] = {"custom_exercise_id": cur.fetchone()[0]}
    connection.commit()
    REFS["Banded Hip Thrust"] = exercise_ref(connection, "Banded Hip Thrust")
    squat = REFS["Squat (Barbell)"]
    save_session(connection, session("3000-01-01", squat, [heavy(120.0)], goal_kg=140.0))
    save_session(connection, session("3000-01-08", squat, [heavy(125.0)], goal_kg=140.0))
    # Logged under the person's own squat, which is linked to the library's: it counts as Squat.
    save_session(connection, session("3000-01-15", REFS["Low-bar Squat"], [heavy(110.0)]))
    pull_up = REFS["Pull-up (Bodyweight)"]
    save_session(connection, session("3000-01-02", pull_up, [bodyweight(8), bodyweight(6)]))
    save_session(connection, session("3000-01-09", pull_up, [bodyweight(10)]))
    save_session(connection, session("3000-01-03", REFS["Banded Hip Thrust"], [heavy(80.0)]))
    yield connection
    clean_test_data(connection)
    connection.close()


@pytest.fixture(scope="module")
def client(conn):
    from traininglogs.api.app import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def unpinned(conn):
    yield
    _no_pins(conn)


def _names(lifts: list[dict]) -> list[str]:
    return [lift["name"] for lift in lifts]


def _ids(lifts: list[dict]) -> list[str]:
    return [lift["library_exercise_id"] or lift["custom_exercise_id"] for lift in lifts]


def test_with_none_pinned_the_six_defaults_come_first_in_order(client) -> None:
    r = client.get("/progress/lifts", headers=HEADERS)
    assert r.status_code == 200
    key_lifts = r.json()["key_lifts"]
    assert _names(key_lifts) == DEFAULTS
    assert _ids(key_lifts) == [REFS[name]["library_exercise_id"] for name in DEFAULTS]


def test_a_lift_gathers_the_sessions_of_custom_exercises_linked_to_it(client) -> None:
    squat = client.get("/progress/lifts", headers=HEADERS).json()["key_lifts"][0]
    assert squat == {
        "library_exercise_id": REFS["Squat (Barbell)"]["library_exercise_id"], "custom_exercise_id": None,
        "name": "Squat (Barbell)", "metric": "estimated_max", "sessions": 3, "latest": 124.7, "best": 141.7,
        "last_date": "3000-01-15", "trend": None,
    }


def test_a_bodyweight_lift_reports_best_reps(client) -> None:
    pull_up = client.get("/progress/lifts", headers=HEADERS).json()["key_lifts"][5]
    assert (pull_up["name"], pull_up["metric"], pull_up["sessions"], pull_up["latest"], pull_up["best"]) == (
        "Pull-up (Bodyweight)", "bodyweight_reps", 2, 10.0, 10.0)


def test_a_default_never_trained_is_listed_with_no_sessions(client) -> None:
    bench = client.get("/progress/lifts", headers=HEADERS).json()["key_lifts"][1]
    assert (bench["name"], bench["sessions"], bench["latest"], bench["best"], bench["last_date"]) == (
        "Bench Press (Barbell)", 0, None, None, None)


def test_lift_detail_points_records_and_goal(client) -> None:
    r = client.get("/progress/lift", params=REFS["Squat (Barbell)"], headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert (body["name"], body["metric"]) == ("Squat (Barbell)", "estimated_max")
    points = body["points"]
    assert [(p["date"], p["value"], p["method"], p["goal_weight_kg"]) for p in points] == [
        ("3000-01-01", 136.0, "rpe", 140.0), ("3000-01-08", 141.7, "rpe", 140.0), ("3000-01-15", 124.7, "rpe", None),
    ]
    assert points[1]["best_set"] == {"number": 1, "weight_kg": 125.0, "reps": 3, "rpe": 9.0}


def test_lift_detail_of_a_bodyweight_lift_counts_reps(client) -> None:
    body = client.get("/progress/lift", params=REFS["Pull-up (Bodyweight)"], headers=HEADERS).json()
    assert body["metric"] == "bodyweight_reps"
    assert [(p["date"], p["value"], p["best_set"]["reps"]) for p in body["points"]] == [
        ("3000-01-02", 8.0, 8), ("3000-01-09", 10.0, 10),
    ]


def test_lift_detail_of_a_custom_exercise(client) -> None:
    body = client.get("/progress/lift", params=REFS["Banded Hip Thrust"], headers=HEADERS).json()
    assert (body["library_exercise_id"], body["custom_exercise_id"], body["name"], body["sessions"]) == (
        None, REFS["Banded Hip Thrust"]["custom_exercise_id"], "Banded Hip Thrust", 1)


@pytest.mark.parametrize("params", [
    {"library_exercise_id": str(uuid.uuid4())},
    {},
    {"library_exercise_id": str(uuid.uuid4()), "custom_exercise_id": str(uuid.uuid4())},
])
def test_lift_detail_for_no_lift_of_yours_is_404(client, params) -> None:
    assert client.get("/progress/lift", params=params, headers=HEADERS).status_code == 404


def test_lift_detail_of_someone_elses_lift_is_404(client) -> None:
    params = REFS["Banded Hip Thrust"]
    assert client.get("/progress/lift", params=params, headers=auth(USER_B_AUTH)).status_code == 404


def test_requires_auth(client) -> None:
    assert client.get("/progress/lifts").status_code == 401


def test_ai_usage_is_the_persons_own_total(client, conn) -> None:
    from traininglogs.db.insert import insert_ai_calls, insert_input

    call = {"step": "extract_exercise", "model": "m", "attempts": 1, "ms": 10}
    assert client.get("/me/ai-usage", headers=auth()).json() == {"total_usd": 0.0}
    insert_ai_calls(conn, USER_A, insert_input(conn, USER_A, "note 1"), [{**call, "cost_usd": 0.0185}, {**call, "cost_usd": 0.002}])
    insert_ai_calls(conn, USER_B, insert_input(conn, USER_B, "note 2"), [{**call, "cost_usd": 0.5}])
    assert client.get("/me/ai-usage", headers=auth()).json() == {"total_usd": 0.0205}
    assert client.get("/me/ai-usage", headers=auth(USER_B_AUTH)).json() == {"total_usd": 0.5}


def test_pinned_lifts_are_saved_shown_in_their_order_and_only_for_that_person(client, unpinned) -> None:
    pins = [REFS["Deadlift (Barbell)"], REFS["Squat (Barbell)"]]
    r = client.put("/me/key-lifts", headers=HEADERS, json={"lifts": pins})
    assert r.status_code == 200
    assert _names(r.json()["key_lifts"]) == ["Deadlift (Barbell)", "Squat (Barbell)"]
    assert _names(client.get("/progress/lifts", headers=HEADERS).json()["key_lifts"]) == [
        "Deadlift (Barbell)", "Squat (Barbell)"]
    assert _names(client.get("/progress/lifts", headers=auth(USER_B_AUTH)).json()["key_lifts"]) == DEFAULTS


def test_a_lift_no_longer_pinned_moves_to_other_lifts(client, unpinned) -> None:
    """Pull-up has two sessions, short of the three an unpinned lift needs; Squat has three."""
    body = client.put("/me/key-lifts", headers=HEADERS, json={"lifts": [REFS["Deadlift (Barbell)"]]}).json()
    assert _names(body["key_lifts"]) == ["Deadlift (Barbell)"]
    assert _names(body["other_lifts"]) == ["Squat (Barbell)"]


def test_a_custom_exercise_can_be_pinned(client, unpinned) -> None:
    hip_thrust = REFS["Banded Hip Thrust"]
    body = client.put("/me/key-lifts", headers=HEADERS, json={"lifts": [hip_thrust, REFS["Squat (Barbell)"]]}).json()
    first = body["key_lifts"][0]
    assert (first["library_exercise_id"], first["custom_exercise_id"], first["name"], first["metric"], first["sessions"]) == (
        None, hip_thrust["custom_exercise_id"], "Banded Hip Thrust", "estimated_max", 1)
    assert _names(body["key_lifts"]) == ["Banded Hip Thrust", "Squat (Barbell)"]


@pytest.mark.parametrize("stranger", ["theirs", "unknown"])
def test_a_pin_that_isnt_your_exercise_is_refused_and_nothing_changes(client, conn, unpinned, stranger) -> None:
    ref = exercise_ref(conn, "Their Own Press", USER_B) if stranger == "theirs" else {"library_exercise_id": str(uuid.uuid4())}
    r = client.put("/me/key-lifts", headers=HEADERS, json={"lifts": [REFS["Squat (Barbell)"], ref]})
    assert r.status_code == 422
    assert _names(client.get("/progress/lifts", headers=HEADERS).json()["key_lifts"]) == DEFAULTS


def test_pinning_none_shows_no_key_lifts(client, unpinned) -> None:
    body = client.put("/me/key-lifts", headers=HEADERS, json={"lifts": []}).json()
    assert body["key_lifts"] == []
    assert _names(body["other_lifts"]) == ["Squat (Barbell)"]


@pytest.mark.parametrize("lifts", [
    "twice",
    [{}],
    [{"library_exercise_id": str(uuid.uuid4()), "custom_exercise_id": str(uuid.uuid4())}],
    [{"library_exercise_id": "not-an-id"}],
])
def test_key_lifts_refuses_a_lift_listed_twice_or_not_exactly_one_exercise(client, unpinned, lifts) -> None:
    if lifts == "twice":
        lifts = [REFS["Squat (Barbell)"], REFS["Squat (Barbell)"]]
    assert client.put("/me/key-lifts", headers=HEADERS, json={"lifts": lifts}).status_code == 422
    assert _names(client.get("/progress/lifts", headers=HEADERS).json()["key_lifts"]) == DEFAULTS
