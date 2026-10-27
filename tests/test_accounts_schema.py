"""What the database itself enforces about owners and links, against the real test DB. Each test
runs in a transaction that is rolled back, so nothing is left behind."""
from __future__ import annotations

import psycopg2
import pytest

from signed_in import TEST_DB_URL
from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.ids import new_id


@pytest.fixture()
def cur():
    conn = get_connection(TEST_DB_URL)
    apply_schema(conn)
    with conn.cursor() as c:
        yield c
    conn.rollback()
    conn.close()


def _user(cur) -> str:
    user = new_id()
    cur.execute("INSERT INTO users (id, auth_id) VALUES (%s, %s)", (user, new_id()))
    return user


def _program(cur, user: str, following: bool = False) -> str:
    program = new_id()
    cur.execute("INSERT INTO programs (id, user_id, name, following) VALUES (%s, %s, 'P', %s)", (program, user, following))
    return program


def _workout(cur, user: str, program: str) -> str:
    workout = new_id()
    cur.execute(
        "INSERT INTO program_workouts (id, user_id, program_id, position) VALUES (%s, %s, %s, 1)", (workout, user, program)
    )
    return workout


def _input(cur, user: str, client_id: str | None = None) -> str:
    input_id = new_id()
    cur.execute(
        "INSERT INTO input_text (id, user_id, content, kind, client_id, checksum) VALUES (%s, %s, 'x', 'manual', %s, 'c')",
        (input_id, user, client_id),
    )
    return input_id


def _session(cur, user: str, input_id: str, **links) -> str:
    session = new_id()
    cur.execute(
        "INSERT INTO workout_sessions (id, user_id, date, dedup_key, input_id, program_workout_id, confirmation_card_id)"
        " VALUES (%s, %s, '3000-01-01', %s, %s, %s, %s)",
        (session, user, links.get("dedup_key", new_id()), input_id, links.get("workout"), links.get("card")),
    )
    return session


def _custom_exercise(cur, user: str, name: str = "My Curl") -> str:
    exercise = new_id()
    cur.execute("INSERT INTO custom_exercises (id, user_id, name) VALUES (%s, %s, %s)", (exercise, user, name))
    return exercise


def _library_exercise(cur) -> str:
    cur.execute("SELECT id::text FROM library_exercises WHERE name = 'Squat (Barbell)'")
    return cur.fetchone()[0]


def _session_exercise(cur, user: str, session: str, library: str | None, custom: str | None) -> None:
    cur.execute(
        "INSERT INTO workout_session_exercises (id, user_id, session_id, position, name, library_exercise_id,"
        " custom_exercise_id) VALUES (%s, %s, %s, 1, 'x', %s, %s)",
        (new_id(), user, session, library, custom),
    )


def _plan_exercise(cur, user: str, workout: str, library: str | None, custom: str | None) -> str:
    plan_exercise = new_id()
    cur.execute(
        "INSERT INTO program_workout_exercises (id, user_id, workout_id, position, name, library_exercise_id,"
        " custom_exercise_id) VALUES (%s, %s, %s, 1, 'x', %s, %s)",
        (plan_exercise, user, workout, library, custom),
    )
    return plan_exercise


def _alternative(cur, user: str, plan_exercise: str, library: str | None, custom: str | None) -> None:
    cur.execute(
        "INSERT INTO program_workout_exercise_alternatives (id, user_id, program_workout_exercise_id, position,"
        " library_exercise_id, custom_exercise_id) VALUES (%s, %s, %s, 1, %s, %s)",
        (new_id(), user, plan_exercise, library, custom),
    )


def _refused(cur, error: type[Exception], insert, *args) -> None:
    """`insert(cur, *args)` raises `error`; the rows made before it stay."""
    cur.execute("SAVEPOINT refused")
    with pytest.raises(error):
        insert(cur, *args)
    cur.execute("ROLLBACK TO SAVEPOINT refused")


def test_an_owner_must_be_a_real_user(cur) -> None:
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        _program(cur, new_id())


def test_a_user_with_data_cannot_be_deleted(cur) -> None:
    user = _user(cur)
    _program(cur, user)
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute("DELETE FROM users WHERE id = %s", (user,))


def test_a_child_cant_belong_to_someone_other_than_its_parents_owner(cur) -> None:
    a, b = _user(cur), _user(cur)
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        _workout(cur, b, _program(cur, a))


def test_a_session_cant_link_to_someone_elses_workout_or_input(cur) -> None:
    a, b = _user(cur), _user(cur)
    workout = _workout(cur, a, _program(cur, a))
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        _session(cur, b, _input(cur, b), workout=workout)
    cur.connection.rollback()
    a, b = _user(cur), _user(cur)
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        _session(cur, b, _input(cur, a))


def test_the_same_note_twice_is_refused_per_person_only(cur) -> None:
    a, b = _user(cur), _user(cur)
    _session(cur, a, _input(cur, a), dedup_key="3000-01-01-abc123")
    _session(cur, b, _input(cur, b), dedup_key="3000-01-01-abc123")  # someone else: fine
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _session(cur, a, _input(cur, a), dedup_key="3000-01-01-abc123")


def test_a_phones_session_id_is_unique_per_person_only(cur) -> None:
    a, b = _user(cur), _user(cur)
    _input(cur, a, client_id="phone-1")
    _input(cur, b, client_id="phone-1")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _input(cur, a, client_id="phone-1")


def test_an_exercise_name_is_one_exercise_ignoring_case_and_spaces(cur) -> None:
    a, b = _user(cur), _user(cur)
    _custom_exercise(cur, a, "Bench Press")
    _custom_exercise(cur, b, "bench press")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _custom_exercise(cur, a, "  bench   PRESS ")


def test_sessions_and_plans_cant_point_at_someone_elses_custom_exercise(cur) -> None:
    a, b = _user(cur), _user(cur)
    theirs, mine = _custom_exercise(cur, a), _custom_exercise(cur, b)
    session = _session(cur, b, _input(cur, b))
    workout = _workout(cur, b, _program(cur, b))
    plan_exercise = _plan_exercise(cur, b, workout, None, mine)
    _refused(cur, psycopg2.errors.ForeignKeyViolation, _session_exercise, b, session, None, theirs)
    _refused(cur, psycopg2.errors.ForeignKeyViolation, _plan_exercise, b, workout, None, theirs)
    _refused(cur, psycopg2.errors.ForeignKeyViolation, _alternative, b, plan_exercise, None, theirs)
    _session_exercise(cur, b, session, None, mine)
    _alternative(cur, b, plan_exercise, None, mine)


def test_sessions_and_plans_point_at_exactly_one_exercise(cur) -> None:
    user = _user(cur)
    library, custom = _library_exercise(cur), _custom_exercise(cur, user)
    session = _session(cur, user, _input(cur, user))
    workout = _workout(cur, user, _program(cur, user))
    plan_exercise = _plan_exercise(cur, user, workout, library, None)
    for neither_or_both in ((None, None), (library, custom)):
        _refused(cur, psycopg2.errors.CheckViolation, _session_exercise, user, session, *neither_or_both)
        _refused(cur, psycopg2.errors.CheckViolation, _plan_exercise, user, workout, *neither_or_both)
        _refused(cur, psycopg2.errors.CheckViolation, _alternative, user, plan_exercise, *neither_or_both)
    _session_exercise(cur, user, session, library, None)
    _alternative(cur, user, plan_exercise, None, custom)


def test_each_person_follows_at_most_one_program(cur) -> None:
    a, b = _user(cur), _user(cur)
    _program(cur, a, following=True)
    _program(cur, b, following=True)
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _program(cur, a, following=True)


def test_one_sign_in_account_is_one_user(cur) -> None:
    auth_id = new_id()
    cur.execute("INSERT INTO users (id, auth_id) VALUES (%s, %s)", (new_id(), auth_id))
    with pytest.raises(psycopg2.errors.UniqueViolation):
        cur.execute("INSERT INTO users (id, auth_id) VALUES (%s, %s)", (new_id(), auth_id))


def test_every_table_but_the_shared_ones_has_a_required_owner(cur) -> None:
    cur.execute(
        """
        SELECT t.table_name, c.is_nullable
        FROM information_schema.tables t
        LEFT JOIN information_schema.columns c
          ON c.table_name = t.table_name AND c.column_name = 'user_id' AND c.table_schema = 'public'
        WHERE t.table_schema = 'public' AND t.table_name NOT IN ('users', 'library_exercises', 'free_exercise_db', 'schema_migrations')
        """
    )
    assert {t: nullable for t, nullable in cur.fetchall()} == {t: "NO" for t in (
        "profiles", "custom_exercises", "input_text", "input_text_confirmation_cards", "ai_call_logs", "feedback",
        "programs", "program_workouts", "program_workout_exercises", "program_workout_exercise_alternatives",
        "workout_sessions",
        "workout_session_warmups", "workout_session_cooldowns", "workout_session_exercises",
        "workout_session_sets",
    )}


def test_row_level_security_is_on_everywhere(cur) -> None:
    cur.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
        " WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity"
    )
    assert cur.fetchall() == []
