"""Programs and workouts, through the API against the real test DB."""
from __future__ import annotations

import os
from datetime import date

import pytest
from fastapi.testclient import TestClient

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.programs import utc_today

from signed_in import clean_test_data, USER_A, USER_B_AUTH, auth

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL
HEADERS = auth()

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


def _program(client, name="Strength", workouts=("Bench", None, "Bench & pull-ups")) -> dict:
    p = client.post("/programs", json={"name": name}, headers=HEADERS).json()
    for w in workouts:
        p = client.post(f"/programs/{p['id']}/workouts", json={"name": w}, headers=HEADERS).json()
    return p


def _session_from(conn, sid: str, day: str, workout_id: str, deload: bool = False) -> None:
    """A session of `workout_id` on `day`, for user A; `sid` only keeps each one's text different."""
    from traininglogs.db.insert import insert_input, insert_session
    from traininglogs.ingest.confirm import build_session_from_extract
    from traininglogs.agent.schemas import TrainingLogLLMExtract

    extract = TrainingLogLLMExtract.model_validate({
        "date": day, "is_deload_week": deload or None,
        "exercises": [{"number": 1, "name": "Squat", "sets": [{"number": 1, "weight_kg": 100.0, "rep_count": {"full": 5, "partial": 0}}]}],
    })
    input_id = insert_input(conn, USER_A, sid, kind="manual")
    insert_session(conn, USER_A, build_session_from_extract(extract, sid), input_id, program_workout_id=workout_id)


class TestPrograms:
    def test_needs_the_api_key(self, client) -> None:
        assert client.get("/programs").status_code == 401

    def test_new_program_is_empty_and_not_followed(self, client) -> None:
        r = client.post("/programs", json={"name": "  Strength "}, headers=HEADERS)
        assert r.status_code == 201
        p = r.json()
        assert p["name"] == "Strength"
        assert p["workouts"] == [] and p["next_workout_id"] is None
        assert p["following"] is False and p["deload_after_days"] == 28

    def test_blank_name_is_rejected(self, client) -> None:
        assert client.post("/programs", json={"name": ""}, headers=HEADERS).status_code == 422

    def test_workouts_are_numbered_in_order_and_next_starts_at_1(self, client) -> None:
        p = _program(client)
        assert [(w["position"], w["name"]) for w in p["workouts"]] == [
            (1, "Bench"), (2, None), (3, "Bench & pull-ups")]
        assert p["next_workout_id"] == p["workouts"][0]["id"]

    def test_following_one_program_stops_following_the_other(self, client) -> None:
        a = _program(client, "A", ())
        b = _program(client, "B", ())
        a = client.post(f"/programs/{a['id']}/follow", headers=HEADERS).json()
        assert a["following"] is True and a["following_since"] == utc_today().isoformat()
        client.post(f"/programs/{b['id']}/follow", headers=HEADERS)
        listed = client.get("/programs", headers=HEADERS).json()
        assert [(p["name"], p["following"]) for p in listed] == [("B", True), ("A", False)]
        b = client.post(f"/programs/{b['id']}/unfollow", headers=HEADERS).json()
        assert b["following"] is False

    def test_update_name_and_deload_days(self, client) -> None:
        p = _program(client, workouts=())
        r = client.patch(f"/programs/{p['id']}", json={"deload_after_days": 21}, headers=HEADERS)
        assert r.json()["deload_after_days"] == 21 and r.json()["name"] == "Strength"
        bad = client.patch(f"/programs/{p['id']}", json={"deload_after_days": 0}, headers=HEADERS)
        assert bad.status_code == 422

    def test_archived_program_is_gone_from_the_app(self, client, conn) -> None:
        p = _program(client)
        assert client.delete(f"/programs/{p['id']}", headers=HEADERS).status_code == 204
        assert client.get(f"/programs/{p['id']}", headers=HEADERS).status_code == 404
        assert client.get("/programs", headers=HEADERS).json() == []
        with conn.cursor() as cur:
            cur.execute("SELECT archived_at IS NOT NULL FROM programs WHERE id = %s", (p["id"],))
            assert cur.fetchone() == (True,)

    def test_unknown_program_is_404(self, client) -> None:
        assert client.get("/programs/nope", headers=HEADERS).status_code == 404
        assert client.post("/programs/nope/workouts", json={}, headers=HEADERS).status_code == 404


class TestWorkouts:
    def test_plan_is_replaced_in_order(self, client) -> None:
        p = _program(client)
        w = p["workouts"][0]["id"]
        plan = [
            {"name": "Squat", "warmup_sets": 2, "working_sets": 3, "target_reps": 2},
            {"name": "Chinups", "working_sets": 1, "amrap": True},
        ]
        p = client.put(f"/workouts/{w}/exercises", json={"exercises": plan}, headers=HEADERS).json()
        assert p["workouts"][0]["exercises"] == [
            {"name": "Squat", "warmup_sets": 2, "working_sets": 3, "target_reps": 2, "amrap": False, "alternatives": []},
            {"name": "Chinups", "warmup_sets": 0, "working_sets": 1, "target_reps": None, "amrap": True, "alternatives": []},
        ]
        p = client.put(f"/workouts/{w}/exercises", json={"exercises": plan[1:]}, headers=HEADERS).json()
        assert [e["name"] for e in p["workouts"][0]["exercises"]] == ["Chinups"]
        assert p["workouts"][1]["exercises"] == []

    def test_alternatives_are_kept_cleaned(self, client) -> None:
        w = _program(client)["workouts"][0]["id"]
        plan = [{"name": "Shoulder Press", "alternatives": [" Bench press ", "", "bench PRESS", "shoulder press", "Dips"]}]
        p = client.put(f"/workouts/{w}/exercises", json={"exercises": plan}, headers=HEADERS).json()
        assert p["workouts"][0]["exercises"][0]["alternatives"] == ["Bench press", "Dips"]

    def test_bad_plan_is_rejected(self, client) -> None:
        w = _program(client)["workouts"][0]["id"]
        for bad in ({"name": "  "}, {"name": "Squat", "working_sets": -1}, {"name": "Squat", "target_reps": 0}):
            r = client.put(f"/workouts/{w}/exercises", json={"exercises": [bad]}, headers=HEADERS)
            assert r.status_code == 422, bad

    def test_warmup_and_cooldown_are_kept(self, client) -> None:
        w = _program(client)["workouts"][0]["id"]
        body = {
            "warmup": [{"name": " Easy cardio ", "duration_seconds": 180}, {"name": "Arm circles", "reps": 10}],
            "cooldown": [{"name": "Stretch"}],
        }
        p = client.put(f"/workouts/{w}/movements", json=body, headers=HEADERS).json()
        assert p["workouts"][0]["warmup"] == [
            {"name": "Easy cardio", "reps": None, "duration_seconds": 180},
            {"name": "Arm circles", "reps": 10, "duration_seconds": None},
        ]
        assert p["workouts"][0]["cooldown"] == [{"name": "Stretch", "reps": None, "duration_seconds": None}]
        assert p["workouts"][1]["warmup"] == []
        bad = client.put(f"/workouts/{w}/movements", json={"warmup": [{"name": " "}]}, headers=HEADERS)
        assert bad.status_code == 422

    def test_rename_and_clear_name(self, client) -> None:
        w = _program(client)["workouts"][0]["id"]
        p = client.patch(f"/workouts/{w}", json={"name": "Push"}, headers=HEADERS).json()
        assert p["workouts"][0]["name"] == "Push"
        p = client.patch(f"/workouts/{w}", json={"name": "  "}, headers=HEADERS).json()
        assert p["workouts"][0]["name"] is None

    def test_reorder_needs_every_workout_once(self, client) -> None:
        p = _program(client)
        ids = [w["id"] for w in p["workouts"]]
        p = client.put(f"/programs/{p['id']}/workout-order", json={"workout_ids": ids[::-1]}, headers=HEADERS).json()
        assert [w["id"] for w in p["workouts"]] == ids[::-1]
        assert [w["position"] for w in p["workouts"]] == [1, 2, 3]
        for bad in (ids[:2], ids + ids[:1], ids[:2] + ["nope"]):
            r = client.put(f"/programs/{p['id']}/workout-order", json={"workout_ids": bad}, headers=HEADERS)
            assert r.status_code == 422, bad

    def test_removing_a_workout_renumbers_the_rest(self, client) -> None:
        p = _program(client)
        first, middle, last = (w["id"] for w in p["workouts"])
        p = client.delete(f"/workouts/{middle}", headers=HEADERS).json()
        assert [(w["id"], w["position"]) for w in p["workouts"]] == [(first, 1), (last, 2)]
        assert client.patch(f"/workouts/{middle}", json={"name": "x"}, headers=HEADERS).status_code == 404

    def test_next_workout_follows_the_latest_session_and_wraps(self, client, conn) -> None:
        p = _program(client)
        w1, w2, w3 = (w["id"] for w in p["workouts"])
        _session_from(conn, "programs-test-001", "3000-01-01", w1)
        p = client.get(f"/programs/{p['id']}", headers=HEADERS).json()
        assert p["next_workout_id"] == w2
        assert p["workouts"][0]["last_done"] == "3000-01-01"
        _session_from(conn, "programs-test-002", "3000-01-03", w3)
        p = client.get(f"/programs/{p['id']}", headers=HEADERS).json()
        assert p["next_workout_id"] == w1

    def test_history_lists_a_session_with_its_program_and_workout(self, client, conn) -> None:
        p = _program(client)
        _session_from(conn, "programs-test-003", "3000-02-01", p["workouts"][1]["id"])
        listed = next(s for s in client.get("/sessions", headers=HEADERS).json() if s["date"] == "3000-02-01")
        assert (listed["program_name"], listed["workout_position"], listed["source_kind"]) == (p["name"], 2, "manual")


class TestTemplates:
    def test_lists_the_starter_templates(self, client) -> None:
        r = client.get("/templates", headers=HEADERS)
        assert r.status_code == 200
        names = [t["name"] for t in r.json()]
        assert names == ["5×5 strength", "Push / pull / legs", "Upper / lower", "Upper / lower / PPL"]
        five = r.json()[0]
        assert five["days"] == "3 days a week"
        assert [e["name"] for e in five["workouts"][1]["exercises"]] == ["Squat", "Overhead press", "Deadlift"]

    def test_needs_the_api_key(self, client) -> None:
        assert client.get("/templates").status_code == 401

    def test_copy_makes_a_program_with_every_workout_and_exercise(self, client) -> None:
        r = client.post("/templates/push-pull-legs/copy", headers=HEADERS)
        assert r.status_code == 201
        p = r.json()
        assert p["name"] == "Push / pull / legs"
        assert p["following"] is False
        assert [w["name"] for w in p["workouts"]] == ["Push", "Pull", "Legs"]
        pull_up = p["workouts"][1]["exercises"][1]
        assert pull_up == {
            "name": "Pull-up", "warmup_sets": 0, "working_sets": 3, "target_reps": None, "amrap": True,
            "alternatives": ["Lat pulldown"],
        }

    def test_copying_twice_gives_two_programs(self, client) -> None:
        client.post("/templates/5x5-strength/copy", headers=HEADERS)
        client.post("/templates/5x5-strength/copy", headers=HEADERS)
        programs = client.get("/programs", headers=HEADERS).json()
        assert [p["name"] for p in programs].count("5×5 strength") == 2

    def test_unknown_template_is_404(self, client) -> None:
        r = client.post("/templates/nope/copy", headers=HEADERS)
        assert r.status_code == 404
        assert r.json()["detail"] == "Couldn't find this template."

    def test_a_failed_copy_leaves_nothing_behind(self, client, conn) -> None:
        from traininglogs.db.programs import create_program

        bad = [{"name": "A", "exercises": [{"name": "Squat", "warmup_sets": -1, "working_sets": 3,
                                           "target_reps": 5, "amrap": False}]}]
        with pytest.raises(Exception):
            create_program(conn, USER_A, "Broken", bad)
        assert client.get("/programs", headers=HEADERS).json() == []


class TestDeload:
    """The deload count, on dates far from any other test's sessions."""

    TODAY = date(2998, 3, 1)

    def _program_with_sessions(self, client, conn, days_ago: list[int], deload_days_ago=(), following_days_ago=None):
        from datetime import timedelta

        p = _program(client, workouts=("A",))
        w = p["workouts"][0]["id"]
        for i, n in enumerate(days_ago):
            _session_from(conn, f"programs-deload-{i}", (self.TODAY - timedelta(days=n)).isoformat(), w, n in deload_days_ago)
        if following_days_ago is not None:
            with conn.cursor() as cur:
                cur.execute("UPDATE programs SET following = true, following_since = %s WHERE id = %s",
                            (self.TODAY - timedelta(days=following_days_ago), p["id"]))
            conn.commit()
        from traininglogs.db.programs import deload_status, get_program

        program = get_program(conn, USER_A, p["id"])
        return deload_status(conn, USER_A, program, self.TODAY)

    def test_due_after_28_days_of_training(self, client, conn) -> None:
        status = self._program_with_sessions(client, conn, [30, 27, 24, 21, 18, 15, 12, 9, 6, 3, 1], following_days_ago=30)
        assert status == {"days_since": 30, "due": True, "in_progress": 0}

    def test_not_due_before_28_days(self, client, conn) -> None:
        status = self._program_with_sessions(client, conn, [20, 15, 10, 5, 2], following_days_ago=20)
        assert status == {"days_since": 20, "due": False, "in_progress": 0}

    def test_a_break_of_7_days_restarts_the_count(self, client, conn) -> None:
        # Trained 40 to 20 days ago, then nothing for 10 days, then again from 10 days ago.
        status = self._program_with_sessions(client, conn, [40, 35, 30, 25, 20, 10, 6, 2], following_days_ago=40)
        assert status["days_since"] == 10 and status["due"] is False

    def test_a_break_still_going_counts_as_zero(self, client, conn) -> None:
        status = self._program_with_sessions(client, conn, [40, 30, 20, 9], following_days_ago=40)
        assert status["days_since"] == 0

    def test_counts_from_the_day_after_the_last_deload(self, client, conn) -> None:
        status = self._program_with_sessions(client, conn, [35, 32, 30, 25, 20, 15, 10, 5, 2], deload_days_ago=(32, 30), following_days_ago=35)
        assert status["days_since"] == 29 and status["due"] is True

    def test_a_deload_under_way_is_not_due(self, client, conn) -> None:
        status = self._program_with_sessions(client, conn, [40, 35, 30, 25, 20, 15, 10, 5, 3, 1], deload_days_ago=(3, 1), following_days_ago=40)
        assert status["in_progress"] == 2 and status["due"] is False
