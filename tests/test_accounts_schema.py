"""What the database itself enforces about owners, against the real test DB. Each test runs in a
transaction that is rolled back, so nothing is left behind."""
from __future__ import annotations

import os
import uuid

import psycopg2
import pytest

from traininglogs.db.db import apply_schema, get_connection

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)


@pytest.fixture()
def cur():
    conn = get_connection(TEST_DB_URL)
    apply_schema(conn)
    with conn.cursor() as c:
        yield c
    conn.rollback()
    conn.close()


def _user(cur) -> str:
    cur.execute("INSERT INTO users (auth_id) VALUES (%s) RETURNING id", (str(uuid.uuid4()),))
    return cur.fetchone()[0]


def _program(cur, user_id: str | None, following: bool = False) -> str:
    program_id = uuid.uuid4().hex
    cur.execute(
        "INSERT INTO programs (id, name, following, user_id) VALUES (%s, 'P', %s, %s)",
        (program_id, following, user_id),
    )
    return program_id


def test_an_owner_must_be_a_real_user(cur) -> None:
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        _program(cur, str(uuid.uuid4()))


def test_a_user_with_data_cannot_be_deleted(cur) -> None:
    user = _user(cur)
    _program(cur, user)
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cur.execute("DELETE FROM users WHERE id = %s", (user,))


def test_one_sign_in_account_is_one_user(cur) -> None:
    auth_id = str(uuid.uuid4())
    cur.execute("INSERT INTO users (auth_id) VALUES (%s)", (auth_id,))
    with pytest.raises(psycopg2.errors.UniqueViolation):
        cur.execute("INSERT INTO users (auth_id) VALUES (%s)", (auth_id,))


def test_each_person_follows_at_most_one_program(cur) -> None:
    a, b = _user(cur), _user(cur)
    _program(cur, a, following=True)
    _program(cur, b, following=True)  # someone else following theirs is fine
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _program(cur, a, following=True)


def test_every_owner_column_is_a_uuid_pointing_at_users(cur) -> None:
    cur.execute(
        """
        SELECT c.table_name, c.data_type,
               EXISTS (SELECT 1 FROM information_schema.referential_constraints r
                       JOIN information_schema.key_column_usage k ON k.constraint_name = r.constraint_name
                       JOIN information_schema.constraint_column_usage u ON u.constraint_name = r.constraint_name
                       WHERE k.table_name = c.table_name AND k.column_name = 'user_id'
                         AND u.table_name = 'users' AND r.delete_rule = 'RESTRICT')
        FROM information_schema.columns c
        WHERE c.table_schema = 'public' AND c.column_name = 'user_id'
        ORDER BY 1
        """
    )
    assert cur.fetchall() == [
        ("extractions", "uuid", True),
        ("program_workouts", "uuid", True),
        ("programs", "uuid", True),
        ("raw_inputs", "uuid", True),
        ("sessions", "uuid", True),
    ]
