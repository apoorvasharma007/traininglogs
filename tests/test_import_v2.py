import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from import_json_to_db_v2 import import_sessions
from traininglogs.db.db import apply_schema, get_connection

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)

OUTPUT_DIR = Path(__file__).parent.parent / "output_training_logs_json"
_ALL_FILES = list(OUTPUT_DIR.rglob("*.json"))
EXPECTED_FILE_COUNT = len(_ALL_FILES)
# Unique session_ids (duplicate files share an id and only one gets inserted)
EXPECTED_SESSION_COUNT = len({
    __import__("json").loads(f.read_text())["session_id"] for f in _ALL_FILES
})


@pytest.fixture(scope="module")
def conn():
    c = get_connection(TEST_DB_URL)
    apply_schema(c)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def clean_db(conn):
    yield
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sessions")
    conn.commit()


def test_import_all_sessions(conn):
    inserted, skipped, failed = import_sessions(conn, OUTPUT_DIR)

    assert failed == 0, f"{failed} session(s) failed Pydantic validation"
    # inserted + skipped = files processed; skipped are duplicate session_ids in the data
    assert inserted + skipped == EXPECTED_FILE_COUNT
    assert inserted == EXPECTED_SESSION_COUNT

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sessions")
        assert cur.fetchone()[0] == EXPECTED_SESSION_COUNT


def test_import_is_idempotent(conn):
    inserted1, _, failed1 = import_sessions(conn, OUTPUT_DIR)
    inserted2, skipped2, failed2 = import_sessions(conn, OUTPUT_DIR)

    assert failed1 == 0
    assert failed2 == 0
    assert inserted1 == EXPECTED_SESSION_COUNT
    assert inserted2 == 0
    assert skipped2 == EXPECTED_FILE_COUNT  # all files skipped on second run

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sessions")
        assert cur.fetchone()[0] == EXPECTED_SESSION_COUNT


def test_import_overwrite_reimports_all(conn):
    import_sessions(conn, OUTPUT_DIR)

    inserted, skipped, failed = import_sessions(conn, OUTPUT_DIR, overwrite=True)

    assert failed == 0
    assert inserted == EXPECTED_SESSION_COUNT
    # duplicate session_ids in the data still get skipped by insert_session's idempotency check
    assert inserted + skipped == EXPECTED_FILE_COUNT

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sessions")
        assert cur.fetchone()[0] == EXPECTED_SESSION_COUNT


def test_import_exercises_and_sets_populated(conn):
    import_sessions(conn, OUTPUT_DIR)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM exercises")
        exercise_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM working_sets")
        working_set_count = cur.fetchone()[0]

    assert exercise_count > 0
    assert working_set_count > 0


def test_import_no_json_files(conn, tmp_path):
    inserted, skipped, failed = import_sessions(conn, tmp_path)

    assert inserted == 0
    assert skipped == 0
    assert failed == 0
