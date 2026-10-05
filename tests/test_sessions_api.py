"""POST /sessions (a session entered in the app) and GET /exercises/last, against the test DB."""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.fetch import get_input_by_client_id, get_session

from signed_in import USER_A, USER_B_AUTH, auth, clean_test_data

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


def body(day: str = FAR + "05", **extra) -> dict:
    return {
        "client_id": uuid.uuid4().hex,
        "date": day,
        "focus": "1 · Bench",
        "duration_minutes": 52,
        "exercises": [
            {
                "name": "Squat",
                "notes": "better depth",
                "warmup_sets": [{"weight_kg": 80, "reps": 3}, {"weight_kg": 100}],
                "sets": [{"weight_kg": 125, "reps": 2, "rpe": 8.5}, {"weight_kg": 125, "reps": 2, "notes": "grind"}],
            },
            {"name": "Chinups", "sets": [{"weight_kg": 0, "reps": 19}]},
        ],
        **extra,
    }


class TestSaveSession:
    def test_saves_a_session_like_any_other(self, client, conn) -> None:
        b = body()
        r = client.post("/sessions", json=b, headers=HEADERS)
        assert r.status_code == 201
        assert r.json()["created"] is True
        session = get_session(conn, USER_A, r.json()["session_id"])
        assert session["focus"] == "1 · Bench" and session["duration_minutes"] == 52
        squat = session["exercises"][0]
        assert squat["name"] == "Squat" and squat["notes"] == "better depth"
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
        b = body(warmup=[{"name": "Easy cardio", "duration_seconds": 180}, {"name": "Arm circles", "reps": 10}],
                 cooldown=[{"name": "Stretch", "duration_seconds": 300}])
        r = client.post("/sessions", json=b, headers=HEADERS)
        session = get_session(conn, USER_A, r.json()["session_id"])
        assert [(m["name"], m["reps"], m["duration_seconds"]) for m in session["warmup"]] == [
            ("Easy cardio", None, 180), ("Arm circles", 10, None)]
        assert [(m["name"], m["duration_seconds"]) for m in session["cooldown"]] == [("Stretch", 300)]

    def test_a_session_under_a_minute_saves_without_a_duration(self, client, conn) -> None:
        r = client.post("/sessions", json=body(duration_minutes=0), headers=HEADERS)
        assert r.status_code == 201
        assert get_session(conn, USER_A, r.json()["session_id"])["duration_minutes"] is None

    def test_sending_again_returns_the_saved_session(self, client, conn) -> None:
        b = body()
        first = client.post("/sessions", json=b, headers=HEADERS).json()
        again = client.post("/sessions", json=b, headers=HEADERS)
        assert again.status_code == 200
        assert again.json() == {"session_id": first["session_id"], "created": False}
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM workout_sessions WHERE date::text LIKE %s", (FAR + "%",))
            assert cur.fetchone()[0] == 1

    def test_two_sessions_on_one_day_are_two_sessions(self, client) -> None:
        a = client.post("/sessions", json=body(), headers=HEADERS).json()
        b = client.post("/sessions", json=body(), headers=HEADERS).json()
        assert a["session_id"] != b["session_id"]

    def test_counts_as_a_planned_workout(self, client, conn) -> None:
        from traininglogs.db.programs import add_workout, create_program

        workout_id = add_workout(conn, USER_A, create_program(conn, USER_A, "sessions-test"), "sessions-test")
        r = client.post("/sessions", json=body(program_workout_id=workout_id), headers=HEADERS)
        with conn.cursor() as cur:
            cur.execute("SELECT program_workout_id::text FROM workout_sessions WHERE id = %s", (r.json()["session_id"],))
            assert cur.fetchone()[0] == workout_id

    def test_unknown_workout_saves_nothing(self, client, conn) -> None:
        r = client.post("/sessions", json=body(program_workout_id="nope"), headers=HEADERS)
        assert r.status_code == 422
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM workout_sessions WHERE date::text LIKE %s", (FAR + "%",))
            assert cur.fetchone()[0] == 0

    @pytest.mark.parametrize("change", [
        {"exercises": []},
        {"exercises": [{"name": "Squat"}]},
        {"exercises": [{"name": "  ", "sets": [{"reps": 1}]}]},
        {"client_id": "not-hex"},
        {"exercises": [{"name": "Squat", "sets": [{"weight_kg": -5, "reps": 1}]}]},
    ])
    def test_bad_sessions_are_rejected(self, client, change) -> None:
        assert client.post("/sessions", json={**body(), **change}, headers=HEADERS).status_code == 422

    def test_keeps_when_it_started_and_ended(self, client, conn) -> None:
        r = client.post("/sessions", json=body(started_at="3001-01-05T10:00:00+05:30",
                                                 ended_at="3001-01-05T11:00:00+05:30"), headers=HEADERS)
        with conn.cursor() as cur:
            cur.execute("SELECT ended_at - started_at FROM workout_sessions WHERE id = %s", (r.json()["session_id"],))
            assert str(cur.fetchone()[0]) == "1:00:00"

    def test_each_exercise_is_one_of_the_persons_own_whatever_the_spelling(self, client, conn) -> None:
        client.post("/sessions", json=body(), headers=HEADERS)
        b = body()
        b["exercises"][0]["name"] = "  squat "
        client.post("/sessions", json=b, headers=HEADERS)
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM user_exercises WHERE user_id = %s ORDER BY name", (USER_A,))
            assert [r[0] for r in cur.fetchall()] == ["Chinups", "Squat"]
            cur.execute("SELECT count(DISTINCT user_exercise_id) FROM workout_session_exercises WHERE name ILIKE '%%squat%%'")
            assert cur.fetchone()[0] == 1

    def test_an_obvious_name_links_to_the_shared_list_and_others_stay_your_own(self, client, conn) -> None:
        b = body()
        b["exercises"].append({"name": "SSB squat", "sets": [{"weight_kg": 100, "reps": 5}]})
        client.post("/sessions", json=b, headers=HEADERS)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ue.name, x.name FROM user_exercises ue LEFT JOIN exercises x ON x.id = ue.exercise_id"
                " WHERE ue.user_id = %s", (USER_A,))
            assert set(cur.fetchall()) == {("Chinups", "Chin-up"), ("SSB squat", None), ("Squat", "Barbell Back Squat")}

    def test_needs_a_pass(self, client) -> None:
        assert client.post("/sessions", json=body()).status_code == 401


class TestLastExercises:
    def test_latest_session_of_each_exercise_ignoring_case(self, client) -> None:
        older = body(FAR + "01")
        older["exercises"][0]["sets"] = [{"weight_kg": 120, "reps": 2}]
        client.post("/sessions", json=older, headers=HEADERS)
        client.post("/sessions", json=body(FAR + "08"), headers=HEADERS)

        r = client.get("/exercises/last", params={"name": ["squat ", "CHINUPS", "Never logged"]}, headers=HEADERS)
        assert r.status_code == 200
        found = {e["name"]: e for e in r.json()}
        assert set(found) == {"Squat", "Chinups"}
        squat = found["Squat"]
        assert squat["date"] == FAR + "08" and squat["notes"] == "better depth"
        assert [(s["weight_kg"], s["reps"]) for s in squat["sets"]] == [(125, 2), (125, 2)]
        assert [(w["weight_kg"], w["reps"]) for w in squat["warmup_sets"]] == [(80, 3), (100, None)]

    def test_no_names_is_an_empty_list(self, client) -> None:
        assert client.get("/exercises/last", headers=HEADERS).json() == []
