import json
import os
from pathlib import Path

import pytest

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.processor.processor_v2 import process_md_file

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)

# Minimal valid markdown — synthetic date far in future to avoid collision with real data
MINIMAL_MD = """\
# Training Log
- Date: 2099-06-15
- Phase: 9
- Week: 1
- Deload: No
- Focus: Push Hypertrophy
- Duration: 60 min

## Exercise 1
**Name:** Bench Press
**Goal:** 80 kg x 3 sets x 8-10 reps
**Rest:** 3 min
### Working Sets
1. 80 x 9 RPE 8 good
2. 80 x 8 RPE 8.5 good
3. 80 x 7 RPE 9 good
"""

EXPECTED_SESSION_ID = "2099-06-15_push-hypertrophy_7"


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
        cur.execute("DELETE FROM sessions WHERE session_id = %s", (EXPECTED_SESSION_ID,))
    conn.commit()


@pytest.fixture
def md_file(tmp_path) -> Path:
    f = tmp_path / "push_hypertrophy.md"
    f.write_text(MINIMAL_MD)
    return f


def test_process_inserts_to_db(md_file, conn, tmp_path):
    process_md_file(md_file, conn, output_dir=tmp_path)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT session_id, focus, phase, week FROM sessions WHERE session_id = %s",
            (EXPECTED_SESSION_ID,),
        )
        row = cur.fetchone()

    assert row is not None
    assert row[0] == EXPECTED_SESSION_ID
    assert row[1] == "Push Hypertrophy"
    assert row[2] == 9
    assert row[3] == 1


def test_process_writes_json_after_db_insert(md_file, conn, tmp_path):
    session = process_md_file(md_file, conn, output_dir=tmp_path)

    expected_path = (
        tmp_path
        / session.program
        / f"phase {session.phase}"
        / f"week {session.week}"
        / f"{session.session_id}.json"
    )
    assert expected_path.exists()

    data = json.loads(expected_path.read_text())
    assert data["session_id"] == EXPECTED_SESSION_ID


def test_process_errors_on_collision(md_file, conn, tmp_path):
    process_md_file(md_file, conn, output_dir=tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        process_md_file(md_file, conn, output_dir=tmp_path)

    assert EXPECTED_SESSION_ID in str(exc_info.value)


def test_json_not_written_on_collision(md_file, conn, tmp_path):
    process_md_file(md_file, conn, output_dir=tmp_path)

    output_dir_2 = tmp_path / "second_run"
    output_dir_2.mkdir()

    with pytest.raises(SystemExit):
        process_md_file(md_file, conn, output_dir=output_dir_2)

    # No JSON should exist in the second output dir
    json_files = list(output_dir_2.rglob("*.json"))
    assert json_files == [], f"JSON written despite collision: {json_files}"


def test_db_row_count_after_single_process(md_file, conn, tmp_path):
    process_md_file(md_file, conn, output_dir=tmp_path)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM exercises WHERE session_id = %s", (EXPECTED_SESSION_ID,)
        )
        assert cur.fetchone()[0] == 1
