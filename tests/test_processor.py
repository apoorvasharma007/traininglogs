import json
import os
from pathlib import Path

import pytest


from traininglogs.db.db import apply_schema, get_connection
from traininglogs.processor.processor import _convert_lbs_to_kg, compute_session_id, process_md_file

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)

# Minimal valid markdown — synthetic date far in future to avoid collision with real data
MINIMAL_MD = """\
# Training Log
- Date: 2099-06-15
- Program: Test Program
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


def _session_id(md_path: Path, date: str) -> str:
    return compute_session_id(md_path.read_text(encoding="utf-8"), date)


class TestComputeSessionId:
    """Identity is the content, not where it came from -- roadmap decision 2026-08-10."""

    def test_the_same_content_produces_the_same_id(self) -> None:
        a = compute_session_id("1. 90kg x 8", "2026-01-01")
        b = compute_session_id("1. 90kg x 8", "2026-01-01")
        assert a == b

    def test_a_trailing_newline_does_not_change_the_id(self) -> None:
        a = compute_session_id("1. 90kg x 8", "2026-01-01")
        b = compute_session_id("1. 90kg x 8\n", "2026-01-01")
        assert a == b

    def test_different_line_endings_do_not_change_the_id(self) -> None:
        a = compute_session_id("line one\nline two", "2026-01-01")
        b = compute_session_id("line one\r\nline two", "2026-01-01")
        assert a == b

    def test_extra_internal_whitespace_does_not_change_the_id(self) -> None:
        a = compute_session_id("1.  90kg   x 8", "2026-01-01")
        b = compute_session_id("1. 90kg x 8", "2026-01-01")
        assert a == b

    def test_different_content_produces_a_different_id(self) -> None:
        a = compute_session_id("1. 90kg x 8", "2026-01-01")
        b = compute_session_id("1. 95kg x 8", "2026-01-01")
        assert a != b

    def test_the_same_content_on_a_different_date_produces_a_different_id(self) -> None:
        a = compute_session_id("1. 90kg x 8", "2026-01-01")
        b = compute_session_id("1. 90kg x 8", "2026-01-02")
        assert a != b

    def test_starts_with_the_date(self) -> None:
        assert compute_session_id("1. 90kg x 8", "2026-01-01").startswith("2026-01-01-")


def test_process_inserts_to_db(md_file, conn, tmp_path):
    expected_id = _session_id(md_file, "2099-06-15")
    process_md_file(md_file, conn, inputs_root=md_file.parent, output_dir=tmp_path)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT session_id, focus, phase, week FROM sessions WHERE session_id = %s",
            (expected_id,),
        )
        row = cur.fetchone()

    assert row is not None
    assert row[0] == expected_id
    assert row[1] == "Push Hypertrophy"
    assert row[2] == 9
    assert row[3] == 1


def test_process_writes_json_after_db_insert(md_file, conn, tmp_path):
    session = process_md_file(md_file, conn, inputs_root=md_file.parent, output_dir=tmp_path)

    expected_path = (
        tmp_path
        / session.program
        / f"phase {session.phase}"
        / f"week {session.week}"
        / f"{session.session_id}.json"
    )
    assert expected_path.exists()

    data = json.loads(expected_path.read_text())
    assert data["session_id"] == _session_id(md_file, "2099-06-15")


def test_process_errors_on_collision(md_file, conn, tmp_path):
    process_md_file(md_file, conn, inputs_root=md_file.parent, output_dir=tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        process_md_file(md_file, conn, inputs_root=md_file.parent, output_dir=tmp_path)

    assert _session_id(md_file, "2099-06-15") in str(exc_info.value)


def test_json_not_written_on_collision(md_file, conn, tmp_path):
    process_md_file(md_file, conn, inputs_root=md_file.parent, output_dir=tmp_path)

    output_dir_2 = tmp_path / "second_run"
    output_dir_2.mkdir()

    with pytest.raises(SystemExit):
        process_md_file(md_file, conn, inputs_root=md_file.parent, output_dir=output_dir_2)

    json_files = list(output_dir_2.rglob("*.json"))
    assert json_files == [], f"JSON written despite collision: {json_files}"


def test_db_row_count_after_single_process(md_file, conn, tmp_path):
    expected_id = _session_id(md_file, "2099-06-15")
    process_md_file(md_file, conn, inputs_root=md_file.parent, output_dir=tmp_path)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM exercises WHERE session_id = %s", (expected_id,)
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
- Program: Test Program
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


@pytest.fixture
def lbs_md_file(tmp_path) -> Path:
    f = tmp_path / "push_lbs.md"
    f.write_text(LBS_MD)
    return f


def test_process_lbs_stores_weight_unit(lbs_md_file, conn, tmp_path):
    lbs_id = _session_id(lbs_md_file, "2099-06-16")
    process_md_file(lbs_md_file, conn, inputs_root=lbs_md_file.parent, output_dir=tmp_path)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT weight_unit FROM sessions WHERE session_id = %s", (lbs_id,)
        )
        assert cur.fetchone()[0] == "lbs"


def test_process_lbs_converts_goal_weight_to_kg(lbs_md_file, conn, tmp_path):
    lbs_id = _session_id(lbs_md_file, "2099-06-16")
    process_md_file(lbs_md_file, conn, inputs_root=lbs_md_file.parent, output_dir=tmp_path)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT goal_weight_kg FROM exercises WHERE session_id = %s AND number = 1",
            (lbs_id,),
        )
        row = cur.fetchone()

    assert row is not None
    assert float(row[0]) == pytest.approx(200.0 * 0.453592, abs=0.01)


def test_process_lbs_json_has_weight_unit_field(lbs_md_file, conn, tmp_path):
    session = process_md_file(lbs_md_file, conn, inputs_root=lbs_md_file.parent, output_dir=tmp_path)

    expected_path = (
        tmp_path
        / session.program
        / f"phase {session.phase}"
        / f"week {session.week}"
        / f"{session.session_id}.json"
    )
    data = json.loads(expected_path.read_text())
    assert data["weight_unit"] == "lbs"


# --- activity set integration tests ---

ACTIVITY_MD = """\
# Training Log
- Date: 2099-07-01
- Program: Test Program
- Phase: 9
- Week: 1
- Deload: No
- Focus: Cardio
- Duration: 30 min

## Exercise 1
**Name:** Treadmill Run
### Activity Sets
1. 20 min 2.5 km HR 145
2. 5 min 500 m HR 160
"""


@pytest.fixture
def activity_md_file(tmp_path) -> Path:
    f = tmp_path / "cardio.md"
    f.write_text(ACTIVITY_MD)
    return f


def test_activity_sets_stored_in_db(activity_md_file, conn, tmp_path):
    activity_id = _session_id(activity_md_file, "2099-07-01")
    process_md_file(activity_md_file, conn, inputs_root=activity_md_file.parent, output_dir=tmp_path)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT duration_seconds, distance_meters, heart_rate_bpm
            FROM working_sets ws
            JOIN exercises e ON e.id = ws.exercise_id
            WHERE e.session_id = %s
            ORDER BY ws.number
            """,
            (activity_id,),
        )
        rows = cur.fetchall()

    assert len(rows) == 2

    # set 1: 20 min → 1200 s, 2.5 km → 2500 m, HR 145
    assert rows[0][0] == 1200
    assert float(rows[0][1]) == pytest.approx(2500.0)
    assert rows[0][2] == 145

    # set 2: 5 min → 300 s, 500 m, HR 160
    assert rows[1][0] == 300
    assert float(rows[1][1]) == pytest.approx(500.0)
    assert rows[1][2] == 160


# --- standalone session (no program/phase/week) ---

STANDALONE_MD = """\
# Training Log
- Date: 2099-08-01
- Duration: 45 min

## Exercise 1
**Name:** Pull-up
**Goal:** 0 kg x 3 sets x 8-10 reps
### Working Sets
1. 0 x 8 RPE 8 good
2. 0 x 7 RPE 8.5 good
"""


@pytest.fixture
def standalone_md_file(tmp_path) -> Path:
    f = tmp_path / "standalone.md"
    f.write_text(STANDALONE_MD)
    return f


def test_standalone_session_inserts_to_db(standalone_md_file, conn, tmp_path):
    standalone_id = _session_id(standalone_md_file, "2099-08-01")
    process_md_file(standalone_md_file, conn, inputs_root=standalone_md_file.parent, output_dir=tmp_path)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT session_id, program, phase, week FROM sessions WHERE session_id = %s",
            (standalone_id,),
        )
        row = cur.fetchone()

    assert row is not None
    assert row[0] == standalone_id
    assert row[1] is None
    assert row[2] is None
    assert row[3] is None


def test_standalone_session_json_goes_to_sessions_dir(standalone_md_file, conn, tmp_path):
    session = process_md_file(standalone_md_file, conn, inputs_root=standalone_md_file.parent, output_dir=tmp_path)

    expected_path = tmp_path / "sessions" / f"{session.session_id}.json"
    assert expected_path.exists()

    data = json.loads(expected_path.read_text())
    assert data["program"] is None
    assert data["phase"] is None
    assert data["week"] is None


# --- unilateral set integration tests ---

UNILATERAL_MD = """\
# Training Log
- Date: 2099-07-02
- Program: Test Program
- Phase: 9
- Week: 1
- Deload: No
- Focus: Arms
- Duration: 45 min

## Exercise 1
**Name:** Dumbbell Curl
**Goal:** 25 kg x 3 sets x 10-12 reps
**Rest:** 2 min
### Working Sets
1. 25 x left 8, right 7 RPE 8 good
2. 25 x left 8 + 1, right 7 + 1 RPE 8.5 good
"""


@pytest.fixture
def unilateral_md_file(tmp_path) -> Path:
    f = tmp_path / "arms.md"
    f.write_text(UNILATERAL_MD)
    return f


def test_unilateral_sets_stored_in_db(unilateral_md_file, conn, tmp_path):
    unilateral_id = _session_id(unilateral_md_file, "2099-07-02")
    process_md_file(unilateral_md_file, conn, inputs_root=unilateral_md_file.parent, output_dir=tmp_path)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT left_reps_full, left_reps_partial, right_reps_full, right_reps_partial
            FROM working_sets ws
            JOIN exercises e ON e.id = ws.exercise_id
            WHERE e.session_id = %s
            ORDER BY ws.number
            """,
            (unilateral_id,),
        )
        rows = cur.fetchall()

    assert len(rows) == 2

    # set 1: 8L/7R, no partials
    assert rows[0][0] == 8
    assert rows[0][1] == 0
    assert rows[0][2] == 7
    assert rows[0][3] == 0

    # set 2: 8L+1/7R+1
    assert rows[1][0] == 8
    assert rows[1][1] == 1
    assert rows[1][2] == 7
    assert rows[1][3] == 1
