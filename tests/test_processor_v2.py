import json
import os
from pathlib import Path

import pytest

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.processor.processor_v2 import _convert_lbs_to_kg, process_md_file

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
        cur.execute("DELETE FROM sessions WHERE session_id LIKE '2099-%'")
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


# --- lbs conversion unit tests (no DB) ---

def test_convert_lbs_to_kg_simple():
    d = {"weight_kg": 200.0}
    result = _convert_lbs_to_kg(d)
    assert result["weight_kg"] == pytest.approx(200.0 * 0.453592, abs=1e-4)


def test_convert_lbs_to_kg_nested():
    d = {
        "exercises": [
            {
                "current_goal": {"weight_kg": 135.0},
                "working_sets": [{"weight_kg": 135.0}, {"weight_kg": 135.0}],
            }
        ]
    }
    result = _convert_lbs_to_kg(d)
    expected = pytest.approx(135.0 * 0.453592, abs=1e-4)
    assert result["exercises"][0]["current_goal"]["weight_kg"] == expected
    assert result["exercises"][0]["working_sets"][0]["weight_kg"] == expected
    assert result["exercises"][0]["working_sets"][1]["weight_kg"] == expected


def test_convert_lbs_to_kg_ignores_none():
    d = {"weight_kg": None, "other": "unchanged"}
    result = _convert_lbs_to_kg(d)
    assert result["weight_kg"] is None
    assert result["other"] == "unchanged"


def test_convert_lbs_to_kg_leaves_non_weight_fields():
    d = {"weight_kg": 100.0, "rpe": 8.0, "notes": "felt strong"}
    result = _convert_lbs_to_kg(d)
    assert result["rpe"] == 8.0
    assert result["notes"] == "felt strong"


# --- lbs integration test ---

LBS_MD = """\
# Training Log
- Date: 2099-06-16
- Phase: 9
- Week: 1
- Deload: No
- Focus: Push
- Duration: 45 min
- Unit: lbs

## Exercise 1
**Name:** Bench Press
**Goal:** 200 lbs x 3 sets x 5-6 reps
**Rest:** 3 min
### Working Sets
1. 200 x 5 RPE 8 good
2. 200 x 5 RPE 8.5 good
"""

LBS_SESSION_ID = "2099-06-16_push_7"


@pytest.fixture
def lbs_md_file(tmp_path) -> Path:
    f = tmp_path / "push_lbs.md"
    f.write_text(LBS_MD)
    return f


def test_process_lbs_stores_weight_unit(lbs_md_file, conn, tmp_path):
    process_md_file(lbs_md_file, conn, output_dir=tmp_path)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT weight_unit FROM sessions WHERE session_id = %s", (LBS_SESSION_ID,)
        )
        assert cur.fetchone()[0] == "lbs"


def test_process_lbs_converts_goal_weight_to_kg(lbs_md_file, conn, tmp_path):
    process_md_file(lbs_md_file, conn, output_dir=tmp_path)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT goal_weight_kg FROM exercises WHERE session_id = %s AND number = 1",
            (LBS_SESSION_ID,),
        )
        row = cur.fetchone()

    assert row is not None
    assert float(row[0]) == pytest.approx(200.0 * 0.453592, abs=0.01)


def test_process_lbs_json_has_weight_unit_field(lbs_md_file, conn, tmp_path):
    session = process_md_file(lbs_md_file, conn, output_dir=tmp_path)

    expected_path = (
        tmp_path
        / session.program
        / f"phase {session.phase}"
        / f"week {session.week}"
        / f"{session.session_id}.json"
    )
    data = json.loads(expected_path.read_text())
    assert data["weight_unit"] == "lbs"
