"""The exercise library and people's own exercises, through the API against the real test DB.
conftest loads the library once."""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from signed_in import auth, clean_test_data
from traininglogs.api.schemas import MyExerciseIn
from traininglogs.db.db import apply_schema, get_connection

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL
HEADERS = auth()
CURL = {"name": "Spider Curl", "primary_muscles": ["Biceps"]}


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


def _library_id(client, name: str) -> str:
    library = client.get("/exercises", headers=HEADERS).json()["library"]
    return next(e["id"] for e in library if e["name"] == name)


def _add(client, **body):
    return client.post("/exercises", json={**CURL, **body}, headers=HEADERS)


class TestMyExerciseIn:
    def test_a_custom_exercise(self) -> None:
        ex = MyExerciseIn(name="  Spider Curl ", primary_muscles=["Biceps"])
        assert ex.name == "Spider Curl"
        assert ex.measures == ["weight", "reps"]
        assert MyExerciseIn.model_validate(ex.model_dump(mode="json")) == ex

    def test_a_linked_one_needs_no_muscle(self) -> None:
        assert MyExerciseIn(name="Shoulder Press", exercise_id=str(uuid.uuid4())).primary_muscles == []

    @pytest.mark.parametrize("body", [{"name": "Spider Curl"}, {"name": "   ", "primary_muscles": ["Biceps"]}])
    def test_refuses(self, body) -> None:
        with pytest.raises(ValidationError):
            MyExerciseIn(**body)

    def test_keeps_other_equipment_text_only_for_other(self) -> None:
        assert MyExerciseIn(**CURL, equipment="other", equipment_other="Rings").equipment_other == "Rings"
        assert MyExerciseIn(**CURL, equipment="cable", equipment_other="Rings").equipment_other is None


def test_lists_the_library_and_your_own(client) -> None:
    client.post("/sessions", headers=HEADERS, json={
        "client_id": uuid.uuid4().hex, "date": "3002-01-05", "duration_minutes": 40,
        "exercises": [{"name": "Squat (Barbell)", "sets": [{"weight_kg": 100, "reps": 5}]},
                      {"name": "Shoulder Press", "sets": [{"weight_kg": 40, "reps": 8}]}],
    })
    body = client.get("/exercises", headers=HEADERS).json()
    assert len(body["library"]) > 100
    mine = {e["name"]: e for e in body["mine"]}
    assert mine["Squat (Barbell)"]["exercise_id"] == _library_id(client, "Squat (Barbell)")
    assert mine["Shoulder Press"]["exercise_id"] is None and mine["Shoulder Press"]["primary_muscles"] == []


def test_adds_a_custom_exercise(client) -> None:
    r = _add(client, secondary_muscles=["Brachialis"], equipment="other", equipment_other="Preacher bench")
    assert r.status_code == 201, r.text
    saved = r.json()
    assert saved["exercise_id"] is None and saved["measures"] == ["weight", "reps"]
    assert saved["equipment_other"] == "Preacher bench"
    assert client.get("/exercises", headers=HEADERS).json()["mine"] == [saved]


@pytest.mark.parametrize(("body", "status"), [
    ({"primary_muscles": ["Bicep"]}, 422),
    ({"movement_patterns": ["Push"]}, 422),
    ({"equipment": "rings"}, 422),
    ({"exercise_id": "not-an-id"}, 422),
    ({"exercise_id": str(uuid.uuid4())}, 422),
    ({"name": "squat (barbell)"}, 409),
])
def test_refuses_a_bad_exercise(client, body, status) -> None:
    assert _add(client, **body).status_code == status
    assert client.get("/exercises", headers=HEADERS).json()["mine"] == []


def test_refuses_a_name_you_already_have_ignoring_case(client) -> None:
    _add(client)
    assert _add(client, name="spider  curl").status_code == 409


def test_changes_renames_links_and_unlinks(client) -> None:
    saved = _add(client).json()
    url = f"/exercises/{saved['id']}"
    renamed = client.put(url, json={**CURL, "name": "Spider Curl (Dumbbell)", "equipment": "dumbbell"}, headers=HEADERS)
    assert renamed.json()["name"] == "Spider Curl (Dumbbell)" and renamed.json()["equipment"] == "dumbbell"
    curl = _library_id(client, "Biceps Curl (Dumbbell)")
    linked = client.put(url, json={**renamed.json(), "exercise_id": curl}, headers=HEADERS).json()
    assert linked["exercise_id"] == curl and linked["primary_muscles"] == ["Biceps"]
    unlinked = client.put(url, json={**linked, "exercise_id": None}, headers=HEADERS).json()
    assert unlinked == renamed.json()


def test_a_library_name_must_link_to_that_exercise(client) -> None:
    saved = _add(client).json()
    url = f"/exercises/{saved['id']}"
    assert client.put(url, json={**CURL, "name": "Squat (Barbell)"}, headers=HEADERS).status_code == 409
    squat = _library_id(client, "Squat (Barbell)")
    r = client.put(url, json={"name": "Squat (Barbell)", "exercise_id": squat}, headers=HEADERS)
    assert r.status_code == 200 and r.json()["exercise_id"] == squat


def test_refuses_renaming_onto_another_of_yours(client) -> None:
    _add(client)
    other = _add(client, name="Bayesian Curl").json()
    assert client.put(f"/exercises/{other['id']}", json=CURL, headers=HEADERS).status_code == 409


@pytest.mark.parametrize("user_exercise_id", [str(uuid.uuid4()), "not-an-id"])
def test_changing_one_that_doesnt_exist(client, user_exercise_id) -> None:
    assert client.put(f"/exercises/{user_exercise_id}", json=CURL, headers=HEADERS).status_code == 404
