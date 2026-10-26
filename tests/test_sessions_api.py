"""POST /sessions (a session entered in the app) and GET /exercises/last, against the test DB."""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.fetch import get_input_by_client_id, get_session

from signed_in import USER_A, USER_B, USER_B_AUTH, auth, clean_test_data, exercise_ref

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL
HEADERS = auth()

# Every session here is dated in 3001 so cleanup can find them.
FAR = "3001-01-"


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


SQUAT, CHIN_UP = "Squat (Barbell)", "Chin-up (Bodyweight)"


def body(conn, day: str = FAR + "05", **extra) -> dict:
    return {
        "client_id": uuid.uuid4().hex,
        "date": day,
        "focus": "1 · Bench",
        "duration_minutes": 52,
        "exercises": [
            {
                **exercise_ref(conn, SQUAT),
                "notes": "better depth",
                "warmup_sets": [{"weight_kg": 80, "reps": 3}, {"weight_kg": 100}],
                "sets": [{"weight_kg": 125, "reps": 2, "rpe": 8.5}, {"weight_kg": 125, "reps": 2, "notes": "grind"}],
            },
            {**exercise_ref(conn, CHIN_UP), "sets": [{"weight_kg": 0, "reps": 19}]},
        ],
        **extra,
    }


class TestSaveSession:
    def test_saves_a_session_like_any_other(self, client, conn) -> None:
        b = body(conn)
        r = client.post("/sessions", json=b, headers=HEADERS)
        assert r.status_code == 201
        assert r.json()["created"] is True
        session = get_session(conn, USER_A, r.json()["session_id"])
        assert session["focus"] == "1 · Bench" and session["duration_minutes"] == 52
        squat = session["exercises"][0]
        # The session keeps the library exercise's name as it was that day.
        assert squat["name"] == SQUAT and squat["notes"] == "better depth"
        assert squat["library_exercise_id"] == exercise_ref(conn, SQUAT)["library_exercise_id"]
        assert [(w["weight_kg"], w["rep_count"]) for w in squat["warmup_sets"]] == [(80, 3), (100, None)]
        assert [(s["weight_kg"], s["reps_full"], s["rpe"], s["notes"]) for s in squat["sets"]] == [
            (125, 2, 8.5, None), (125, 2, None, "grind")]
        assert get_input_by_client_id(conn, USER_A, b["client_id"])["kind"] == "manual"
        # Saved straight from its input: no confirmation card.
        with conn.cursor() as cur:
            cur.execute("SELECT confirmation_card_id FROM workout_sessions WHERE id = %s", (r.json()["session_id"],))
            assert cur.fetchone()[0] is None
            cur.execute("SELECT count(*) FROM input_text_confirmation_cards")
            assert cur.fetchone()[0] == 0

    def test_saves_warmup_and_cooldown(self, client, conn) -> None:
        b = body(conn, warmup=[{"name": "Easy cardio", "duration_seconds": 180}, {"name": "Arm circles", "reps": 10}],
                 cooldown=[{"name": "Stretch", "duration_seconds": 300}])
        r = client.post("/sessions", json=b, headers=HEADERS)
        session = get_session(conn, USER_A, r.json()["session_id"])
        assert [(m["name"], m["reps"], m["duration_seconds"]) for m in session["warmup"]] == [
            ("Easy cardio", None, 180), ("Arm circles", 10, None)]
        assert [(m["name"], m["duration_seconds"]) for m in session["cooldown"]] == [("Stretch", 300)]

    def test_a_session_under_a_minute_saves_without_a_duration(self, client, conn) -> None:
        r = client.post("/sessions", json=body(conn, duration_minutes=0), headers=HEADERS)
        assert r.status_code == 201
        assert get_session(conn, USER_A, r.json()["session_id"])["duration_minutes"] is None

    def test_sending_again_returns_the_saved_session(self, client, conn) -> None:
        b = body(conn)
        first = client.post("/sessions", json=b, headers=HEADERS).json()
        again = client.post("/sessions", json=b, headers=HEADERS)
        assert again.status_code == 200
        assert again.json() == {"session_id": first["session_id"], "created": False}
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM workout_sessions WHERE date::text LIKE %s", (FAR + "%",))
            assert cur.fetchone()[0] == 1

    def test_a_resend_racing_the_first_send_returns_the_same_session(self, conn) -> None:
        """After a timeout the phone sends again while the first send may still be saving."""
        from concurrent.futures import ThreadPoolExecutor

        from traininglogs.api.schemas import ManualSessionIn
        from traininglogs.ingest.manual import save_manual_session

        b = ManualSessionIn.model_validate(body(conn)).model_dump(mode="json")

        def send(_):
            c = get_connection(TEST_DB_URL)
            try:
                return save_manual_session(c, USER_A, b)
            finally:
                c.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(send, range(4)))
        assert len({session_id for session_id, _ in results}) == 1
        assert sum(created for _, created in results) == 1

    def test_two_sessions_on_one_day_are_two_sessions(self, client, conn) -> None:
        a = client.post("/sessions", json=body(conn), headers=HEADERS).json()
        b = client.post("/sessions", json=body(conn), headers=HEADERS).json()
        assert a["session_id"] != b["session_id"]

    def test_counts_as_a_planned_workout(self, client, conn) -> None:
        from traininglogs.db.programs import add_workout, create_program

        workout_id = add_workout(conn, USER_A, create_program(conn, USER_A, "sessions-test"), "sessions-test")
        r = client.post("/sessions", json=body(conn, program_workout_id=workout_id), headers=HEADERS)
        with conn.cursor() as cur:
            cur.execute("SELECT program_workout_id::text FROM workout_sessions WHERE id = %s", (r.json()["session_id"],))
            assert cur.fetchone()[0] == workout_id

    def test_unknown_workout_saves_nothing(self, client, conn) -> None:
        r = client.post("/sessions", json=body(conn, program_workout_id="nope"), headers=HEADERS)
        assert r.status_code == 422
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM workout_sessions WHERE date::text LIKE %s", (FAR + "%",))
            assert cur.fetchone()[0] == 0

    @pytest.mark.parametrize("exercise", [
        {"sets": [{"reps": 1}]},
        {"library_exercise_id": "not-an-id", "sets": [{"reps": 1}]},
        {"library_exercise_id": str(uuid.uuid4()), "custom_exercise_id": str(uuid.uuid4()), "sets": [{"reps": 1}]},
    ])
    def test_an_exercise_not_picked_is_rejected(self, client, conn, exercise) -> None:
        assert client.post("/sessions", json={**body(conn), "exercises": [exercise]}, headers=HEADERS).status_code == 422

    def test_bad_sessions_are_rejected(self, client, conn) -> None:
        squat = exercise_ref(conn, SQUAT)
        for change in (
            {"exercises": []},
            {"exercises": [squat]},
            {"client_id": "not-hex"},
            {"exercises": [{**squat, "sets": [{"weight_kg": -5, "reps": 1}]}]},
        ):
            assert client.post("/sessions", json={**body(conn), **change}, headers=HEADERS).status_code == 422, change

    def test_an_unknown_or_someone_elses_exercise_saves_nothing(self, client, conn) -> None:
        theirs = exercise_ref(conn, "Their Own Curl", USER_B)
        for ref in (theirs, {"library_exercise_id": str(uuid.uuid4())}):
            b = body(conn)
            b["exercises"][0] = {**ref, "sets": [{"weight_kg": 20, "reps": 10}]}
            r = client.post("/sessions", json=b, headers=HEADERS)
            assert r.status_code == 422, ref
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM input_text WHERE user_id = %s", (USER_A,))
            assert cur.fetchone()[0] == 0

    def test_keeps_when_it_started_and_ended(self, client, conn) -> None:
        r = client.post("/sessions", json=body(conn, started_at="3001-01-05T10:00:00+05:30",
                                                 ended_at="3001-01-05T11:00:00+05:30"), headers=HEADERS)
        with conn.cursor() as cur:
            cur.execute("SELECT ended_at - started_at FROM workout_sessions WHERE id = %s", (r.json()["session_id"],))
            assert str(cur.fetchone()[0]) == "1:00:00"

    def test_saving_never_makes_a_custom_exercise(self, client, conn) -> None:
        client.post("/sessions", json=body(conn), headers=HEADERS)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM custom_exercises WHERE user_id = %s", (USER_A,))
            assert cur.fetchone()[0] == 0

    def test_needs_a_pass(self, client, conn) -> None:
        assert client.post("/sessions", json=body(conn)).status_code == 401


class TestLastExercises:
    def test_latest_session_of_each_exercise(self, client, conn) -> None:
        older = body(conn, FAR + "01")
        older["exercises"][0]["sets"] = [{"weight_kg": 120, "reps": 2}]
        client.post("/sessions", json=older, headers=HEADERS)
        client.post("/sessions", json=body(conn, FAR + "08"), headers=HEADERS)
        squat, chin_up = exercise_ref(conn, SQUAT), exercise_ref(conn, CHIN_UP)
        never = exercise_ref(conn, "Never Logged")

        r = client.get("/exercises/last", params={
            "library_exercise_id": [squat["library_exercise_id"], chin_up["library_exercise_id"]],
            "custom_exercise_id": [never["custom_exercise_id"]],
        }, headers=HEADERS)
        assert r.status_code == 200
        found = {e["name"]: e for e in r.json()}
        assert set(found) == {SQUAT, CHIN_UP}
        last = found[SQUAT]
        assert last["library_exercise_id"] == squat["library_exercise_id"]
        assert last["date"] == FAR + "08" and last["notes"] == "better depth"
        assert [(s["weight_kg"], s["reps"]) for s in last["sets"]] == [(125, 2), (125, 2)]
        assert [(w["weight_kg"], w["reps"]) for w in last["warmup_sets"]] == [(80, 3), (100, None)]

    def test_a_custom_exercise_linked_to_the_library_counts_as_it(self, client, conn) -> None:
        squat = exercise_ref(conn, SQUAT)
        mine = exercise_ref(conn, "My Squat")
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE custom_exercises SET linked_library_exercise_id = %s WHERE id = %s",
                (squat["library_exercise_id"], mine["custom_exercise_id"]),
            )
        conn.commit()
        b = body(conn, FAR + "08")
        b["exercises"] = [{**mine, "sets": [{"weight_kg": 130, "reps": 1}]}]
        client.post("/sessions", json=b, headers=HEADERS)

        r = client.get("/exercises/last", params={"library_exercise_id": squat["library_exercise_id"]}, headers=HEADERS)
        assert [(e["library_exercise_id"], e["name"], e["sets"][0]["weight_kg"]) for e in r.json()] == [
            (squat["library_exercise_id"], "My Squat", 130)]

    def test_nothing_asked_is_an_empty_list(self, client) -> None:
        assert client.get("/exercises/last", headers=HEADERS).json() == []
