"""The exercise library file, its loader, and what the database refuses, against the real test DB.
conftest loads the library once; each test here runs in a transaction that is rolled back."""
from __future__ import annotations

import copy
import re

import psycopg2
import pytest

from signed_in import TEST_DB_URL
from traininglogs.db import library
from traininglogs.db.db import get_connection
from traininglogs.db.ids import new_id

LIBRARY = library.read_library()


@pytest.fixture()
def cur():
    conn = get_connection(TEST_DB_URL)
    with conn.cursor() as c:
        yield c
    conn.rollback()
    conn.close()


def _exercise(**changes) -> dict:
    return {**copy.deepcopy(LIBRARY[0]), **changes}


class TestTheFile:
    def test_has_no_problems(self) -> None:
        assert library.check_library(LIBRARY) == []

    def test_every_starter_row_has_a_new_name_with_its_old_name_as_an_other_name(self) -> None:
        by_name = {e["name"]: e for e in LIBRARY}
        assert len(library.STARTER_RENAMES) == len(set(library.STARTER_RENAMES.values())) == 32
        for old, new in library.STARTER_RENAMES.items():
            assert old.lower() in by_name[new]["other_names"]

    @pytest.mark.parametrize("field", ["equipment", "measures", "primary_muscles"])
    def test_required_fields(self, field) -> None:
        assert f"{LIBRARY[0]['name']}: {field} is required" in library.check_library([_exercise(**{field: None})])

    def test_a_name_twice_ignoring_case(self) -> None:
        problems = library.check_library([_exercise(), _exercise(name=LIBRARY[0]["name"].upper())])
        assert any("more than once" in p for p in problems)

    def test_other_names_are_lower_case(self) -> None:
        assert any("isn't lower case" in p for p in library.check_library([_exercise(other_names=["Bench"])]))

    def test_an_other_name_can_be_on_several_exercises(self) -> None:
        a = _exercise(name="A", other_names=["leg curl"])
        b = _exercise(name="B", other_names=["leg curl"], free_exercise_db_id=None)
        assert not any("leg curl" in p for p in library.check_library([a, b]))

    def test_an_unknown_field(self) -> None:
        assert any("unknown field muscles" in p for p in library.check_library([_exercise(muscles=["Abs"])]))


class TestLoaded:
    def test_every_exercise_in_the_file_is_in_the_database(self, cur) -> None:
        cur.execute("SELECT name FROM exercises")
        assert {r[0] for r in cur.fetchall()} == {e["name"] for e in LIBRARY}

    def test_free_exercise_db_matches_the_pinned_file(self, cur) -> None:
        cur.execute("SELECT count(*) FROM free_exercise_db")
        assert cur.fetchone()[0] == len(library.read_free_exercise_db())

    def test_loading_again_changes_nothing(self, cur) -> None:
        theirs = library.load_free_exercise_db(cur, library.read_free_exercise_db())
        ours = library.load_library(cur, LIBRARY)
        assert (theirs["added"], theirs["updated"]) == ([], [])
        assert (ours["renamed"], ours["added"], ours["updated"], ours["not_in_file"]) == ([], [], [], [])

    def test_never_deletes_and_reports_what_the_file_lacks(self, cur) -> None:
        dropped = next(e for e in LIBRARY if e["name"] not in library.STARTER_RENAMES.values())
        report = library.load_library(cur, [e for e in LIBRARY if e is not dropped])
        assert report["not_in_file"] == [dropped["name"]]
        cur.execute("SELECT count(*) FROM exercises WHERE name = %s", (dropped["name"],))
        assert cur.fetchone()[0] == 1


class TestStarterRows:
    def test_renamed_row_keeps_its_id_and_its_links(self, cur) -> None:
        cur.execute("UPDATE exercises SET name = 'Leg Curl' WHERE name = 'Leg Curl (Machine, Lying)' RETURNING id")
        row_id = cur.fetchone()[0]
        user = new_id()
        cur.execute("INSERT INTO users (id, auth_id) VALUES (%s, %s)", (user, new_id()))
        cur.execute(
            "INSERT INTO user_exercises (id, user_id, name, exercise_id) VALUES (%s, %s, 'leg curls', %s)",
            (new_id(), user, row_id),
        )

        report = library.load_library(cur, LIBRARY)

        assert report["renamed"] == ["Leg Curl -> Leg Curl (Machine, Lying)"]
        cur.execute("SELECT id FROM exercises WHERE name = 'Leg Curl (Machine, Lying)'")
        assert cur.fetchone()[0] == row_id
        cur.execute("SELECT exercise_id FROM user_exercises WHERE user_id = %s", (user,))
        assert cur.fetchone()[0] == row_id

    def test_refused_when_the_new_name_is_already_a_separate_row(self, cur) -> None:
        cur.execute("INSERT INTO exercises (id, name, equipment) VALUES (%s, 'Plank', 'bodyweight')", (new_id(),))
        with pytest.raises(library.LibraryError, match="Plank"):
            library.load_library(cur, LIBRARY)


class TestTheDatabaseRefuses:
    @pytest.mark.parametrize("column, value", [
        ("primary_muscles", ["Side Delt"]),
        ("secondary_muscles", ["Pecs"]),
        ("joint_actions", ["shoulder press"]),
        ("patterns", ["Push"]),
        ("measures", ["sets"]),
    ])
    def test_a_value_not_on_the_list(self, cur, column, value) -> None:
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(f"UPDATE exercises SET {column} = %s WHERE name = %s", (value, LIBRARY[0]["name"]))

    def test_equipment_not_on_the_list(self, cur) -> None:
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute("UPDATE exercises SET equipment = 'sandbag' WHERE name = %s", (LIBRARY[0]["name"],))

    def test_a_free_exercise_db_id_that_doesnt_exist(self, cur) -> None:
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            cur.execute("UPDATE exercises SET free_exercise_db_id = 'Nope' WHERE name = %s", (LIBRARY[0]["name"],))

    def test_one_of_theirs_linked_to_two_of_ours(self, cur) -> None:
        taken = next(e for e in LIBRARY if e.get("free_exercise_db_id"))
        other = next(e for e in LIBRARY if not e.get("free_exercise_db_id"))
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute(
                "UPDATE exercises SET free_exercise_db_id = %s WHERE name = %s",
                (taken["free_exercise_db_id"], other["name"]),
            )

    def test_the_loader_names_the_exercise_the_database_refused(self, cur) -> None:
        bad = copy.deepcopy(LIBRARY)
        bad[0]["primary_muscles"] = ["Side Delt"]
        with pytest.raises(library.LibraryError, match=re.escape(LIBRARY[0]["name"])):
            library.load_library(cur, bad)
