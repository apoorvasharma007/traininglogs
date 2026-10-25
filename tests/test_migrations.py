"""Schema change files (db/db.py): each runs once per database, in number order, and a file that
already ran can't be edited. Each test runs in a schema of its own, so the real tables are untouched."""
from __future__ import annotations

from pathlib import Path

import psycopg2
import pytest

from signed_in import TEST_DB_URL
from traininglogs.db.db import apply_schema, get_connection, pending_migrations


@pytest.fixture
def scratch():
    conn = get_connection(TEST_DB_URL)
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS migrations_test CASCADE; CREATE SCHEMA migrations_test")
        cur.execute("SET search_path TO migrations_test")
    conn.commit()
    yield conn
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA migrations_test CASCADE")
    conn.commit()
    conn.close()


def write(folder: Path, name: str, sql: str) -> None:
    (folder / name).write_text(sql)


def columns(conn, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = 'migrations_test' AND table_name = %s ORDER BY ordinal_position",
            (table,),
        )
        return [r[0] for r in cur.fetchall()]


def exists(conn, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"migrations_test.{table}",))
        return cur.fetchone()[0]


def test_files_run_once_in_number_order(scratch, tmp_path) -> None:
    write(tmp_path, "0002_add_note.sql", "ALTER TABLE lifts ADD COLUMN note TEXT;")
    write(tmp_path, "0001_make_lifts.sql", "CREATE TABLE lifts (id INT);")
    assert apply_schema(scratch, folder=tmp_path) == ["0001_make_lifts.sql", "0002_add_note.sql"]
    assert apply_schema(scratch, folder=tmp_path) == []
    assert columns(scratch, "lifts") == ["id", "note"]
    with scratch.cursor() as cur:
        cur.execute("SELECT version, name FROM schema_migrations ORDER BY version")
        assert cur.fetchall() == [(1, "0001_make_lifts.sql"), (2, "0002_add_note.sql")]


def test_a_new_file_runs_where_the_others_already_ran(scratch, tmp_path) -> None:
    write(tmp_path, "0001_make_lifts.sql", "CREATE TABLE lifts (id INT);")
    apply_schema(scratch, folder=tmp_path)
    write(tmp_path, "0002_add_note.sql", "ALTER TABLE lifts ADD COLUMN note TEXT;")
    assert [p.name for p in pending_migrations(scratch, tmp_path)] == ["0002_add_note.sql"]
    assert apply_schema(scratch, folder=tmp_path) == ["0002_add_note.sql"]


def test_an_edited_file_that_already_ran_is_refused(scratch, tmp_path) -> None:
    write(tmp_path, "0001_make_lifts.sql", "CREATE TABLE lifts (id INT);")
    apply_schema(scratch, folder=tmp_path)
    write(tmp_path, "0001_make_lifts.sql", "CREATE TABLE lifts (id INT, note TEXT);")
    with pytest.raises(RuntimeError, match="0001_make_lifts.sql changed after it ran on this database"):
        apply_schema(scratch, folder=tmp_path)


def test_a_failing_file_leaves_the_database_as_it_was(scratch, tmp_path) -> None:
    write(tmp_path, "0001_make_lifts.sql", "CREATE TABLE lifts (id INT);")
    write(tmp_path, "0002_broken.sql", "ALTER TABLE no_such_table ADD COLUMN note TEXT;")
    with pytest.raises(psycopg2.errors.UndefinedTable):
        apply_schema(scratch, folder=tmp_path)
    scratch.rollback()
    assert (exists(scratch, "lifts"), exists(scratch, "schema_migrations")) == (False, False)


def test_the_dry_run_writes_nothing(scratch, tmp_path) -> None:
    write(tmp_path, "0001_make_lifts.sql", "CREATE TABLE lifts (id INT);")
    scratch.set_session(readonly=True)
    assert [p.name for p in pending_migrations(scratch, tmp_path)] == ["0001_make_lifts.sql"]
    scratch.rollback()
    scratch.set_session(readonly=False)
    assert exists(scratch, "schema_migrations") is False


@pytest.mark.parametrize("name", ["make_lifts.sql", "1_make_lifts.sql", "0001-make-lifts.sql"])
def test_a_badly_named_file_is_refused(scratch, tmp_path, name) -> None:
    write(tmp_path, name, "CREATE TABLE lifts (id INT);")
    with pytest.raises(ValueError, match="name it NNNN_what_it_does.sql"):
        apply_schema(scratch, folder=tmp_path)


def test_two_files_with_one_number_are_refused(scratch, tmp_path) -> None:
    write(tmp_path, "0001_make_lifts.sql", "CREATE TABLE lifts (id INT);")
    write(tmp_path, "0001_make_notes.sql", "CREATE TABLE notes (id INT);")
    with pytest.raises(ValueError, match="share a number"):
        apply_schema(scratch, folder=tmp_path)


def test_the_test_database_has_run_every_file() -> None:
    conn = get_connection(TEST_DB_URL)
    try:
        assert pending_migrations(conn) == []
    finally:
        conn.close()
