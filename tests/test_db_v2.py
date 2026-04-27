import json
import os

import pytest

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.insert_v2 import insert_session
from traininglogs.models.models_v2 import (
    Exercise,
    Goal,
    LLPDetails,
    LLPTechnique,
    MyoRep,
    MyoRepDetails,
    MyoRepsTechnique,
    RepCount,
    RepQualityAssessment,
    RepRange,
    TrainingSession,
    WarmupSet,
    WorkingSet,
)

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)


def make_session(session_id: str = "test-session-v2-001") -> TrainingSession:
    return TrainingSession(
        data_model_version="0.0.1",
        data_model_type="TrainingSession",
        session_id=session_id,
        user_id="7",
        user_name="Apoorva Sharma",
        date="2026-01-01",
        program="Test Program",
        program_author="Test Author",
        program_length_weeks=12,
        phase=1,
        week=1,
        is_deload_week=False,
        focus="Pull Hypertrophy",
        session_duration_minutes=90,
        exercises=[
            Exercise(
                number=1,
                name="Lat Pulldown",
                notes="felt strong",
                warmup_notes="Pyramid",
                form_cues=["lean back 15 degrees", "squeeze lats"],
                target_muscle_groups=None,
                rep_tempo=None,
                current_goal=Goal(
                    weight_kg=55.0,
                    sets=3,
                    rep_range=RepRange(min=10, max=12),
                    rest_minutes=2,
                ),
                warmup_sets=[
                    WarmupSet(number=1, weight_kg=40.0, rep_count=6, notes=None),
                ],
                working_sets=[
                    WorkingSet(
                        number=1,
                        weight_kg=55.0,
                        rep_count=RepCount(full=12, partial=0),
                        rpe=8.0,
                        rep_quality_assessment=RepQualityAssessment.GOOD,
                        actual_rest_minutes=None,
                        notes=None,
                        failure_technique=None,
                    ),
                    WorkingSet(
                        number=2,
                        weight_kg=55.0,
                        rep_count=RepCount(full=10, partial=2),
                        rpe=10.0,
                        rep_quality_assessment=RepQualityAssessment.PERFECT,
                        actual_rest_minutes=None,
                        notes="last set was hard",
                        failure_technique=MyoRepsTechnique(
                            technique_type="MyoReps",
                            details=MyoRepDetails(
                                mini_sets=[
                                    MyoRep(number=1, rep_count=RepCount(full=4, partial=0)),
                                    MyoRep(number=2, rep_count=RepCount(full=3, partial=0)),
                                ]
                            ),
                        ),
                    ),
                ],
            ),
            Exercise(
                number=2,
                name="Cable Row",
                notes=None,
                warmup_notes="Pyramid",
                form_cues=["sit upright", "squeeze shoulder blades"],
                target_muscle_groups=None,
                rep_tempo=None,
                current_goal=Goal(
                    weight_kg=50.0,
                    sets=3,
                    rep_range=RepRange(min=12, max=15),
                    rest_minutes=2,
                ),
                warmup_sets=None,
                working_sets=[
                    WorkingSet(
                        number=1,
                        weight_kg=50.0,
                        rep_count=RepCount(full=14, partial=0),
                        rpe=9.0,
                        rep_quality_assessment=RepQualityAssessment.GOOD,
                        actual_rest_minutes=None,
                        notes=None,
                        failure_technique=None,
                    ),
                    WorkingSet(
                        number=2,
                        weight_kg=50.0,
                        rep_count=RepCount(full=12, partial=0),
                        rpe=10.0,
                        rep_quality_assessment=None,
                        actual_rest_minutes=None,
                        notes=None,
                        failure_technique=LLPTechnique(
                            technique_type="LLP",
                            details=LLPDetails(partial_rep_count=5),
                        ),
                    ),
                ],
            ),
            Exercise(
                number=3,
                name="Face Pull",
                notes=None,
                warmup_notes=None,
                form_cues=[],
                target_muscle_groups=None,
                rep_tempo=None,
                current_goal=None,
                # None entry in list — exercises sometimes have this in real data
                warmup_sets=[],
                working_sets=[
                    WorkingSet(
                        number=1,
                        weight_kg=20.0,
                        rep_count=RepCount(full=15, partial=0),
                        rpe=None,
                        rep_quality_assessment=None,
                        actual_rest_minutes=None,
                        notes=None,
                        failure_technique=None,
                    ),
                ],
            ),
        ],
    )


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


def test_insert_session_row_counts(conn):
    insert_session(conn, make_session())

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sessions WHERE session_id = 'test-session-v2-001'")
        assert cur.fetchone()[0] == 1

        cur.execute("SELECT COUNT(*) FROM exercises WHERE session_id = 'test-session-v2-001'")
        assert cur.fetchone()[0] == 3

        cur.execute(
            "SELECT COUNT(*) FROM working_sets WHERE exercise_id IN "
            "(SELECT id FROM exercises WHERE session_id = 'test-session-v2-001')"
        )
        assert cur.fetchone()[0] == 5

        cur.execute(
            "SELECT COUNT(*) FROM warmup_sets WHERE exercise_id IN "
            "(SELECT id FROM exercises WHERE session_id = 'test-session-v2-001')"
        )
        assert cur.fetchone()[0] == 1


def test_insert_session_fields(conn):
    insert_session(conn, make_session())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT date, phase, week, focus, duration_minutes, user_id, user_name "
            "FROM sessions WHERE session_id = 'test-session-v2-001'"
        )
        row = cur.fetchone()

    assert str(row[0]) == "2026-01-01"
    assert row[1] == 1
    assert row[2] == 1
    assert row[3] == "Pull Hypertrophy"
    assert row[4] == 90
    assert row[5] == "7"
    assert row[6] == "Apoorva Sharma"


def test_insert_exercise_with_goal(conn):
    insert_session(conn, make_session())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT goal_weight_kg, goal_sets, goal_rep_min, goal_rep_max, goal_rest_min, form_cues "
            "FROM exercises WHERE session_id = 'test-session-v2-001' AND number = 1"
        )
        row = cur.fetchone()

    assert float(row[0]) == 55.0
    assert row[1] == 3
    assert row[2] == 10
    assert row[3] == 12
    assert row[4] == 2
    assert row[5] == ["lean back 15 degrees", "squeeze lats"]


def test_insert_exercise_without_goal(conn):
    insert_session(conn, make_session())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT goal_weight_kg, goal_sets, goal_rep_min FROM exercises "
            "WHERE session_id = 'test-session-v2-001' AND number = 3"
        )
        row = cur.fetchone()

    assert row[0] is None
    assert row[1] is None
    assert row[2] is None


def test_insert_working_set_partial_reps(conn):
    insert_session(conn, make_session())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT reps_full, reps_partial FROM working_sets WHERE exercise_id = "
            "(SELECT id FROM exercises WHERE session_id = 'test-session-v2-001' AND number = 1) "
            "AND number = 2"
        )
        row = cur.fetchone()

    assert row[0] == 10
    assert row[1] == 2


def test_insert_working_set_myo_reps_failure_technique(conn):
    insert_session(conn, make_session())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT failure_technique FROM working_sets WHERE exercise_id = "
            "(SELECT id FROM exercises WHERE session_id = 'test-session-v2-001' AND number = 1) "
            "AND number = 2"
        )
        ft = cur.fetchone()[0]

    assert ft["technique_type"] == "MyoReps"
    assert len(ft["details"]["mini_sets"]) == 2


def test_insert_working_set_llp_failure_technique(conn):
    insert_session(conn, make_session())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT failure_technique FROM working_sets WHERE exercise_id = "
            "(SELECT id FROM exercises WHERE session_id = 'test-session-v2-001' AND number = 2) "
            "AND number = 2"
        )
        ft = cur.fetchone()[0]

    assert ft["technique_type"] == "LLP"
    assert ft["details"]["partial_rep_count"] == 5


def test_insert_working_set_null_rpe_and_rep_quality(conn):
    insert_session(conn, make_session())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT rpe, rep_quality FROM working_sets WHERE exercise_id = "
            "(SELECT id FROM exercises WHERE session_id = 'test-session-v2-001' AND number = 3)"
        )
        row = cur.fetchone()

    assert row[0] is None
    assert row[1] is None


def test_insert_exercise_with_no_warmup_sets(conn):
    insert_session(conn, make_session())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM warmup_sets WHERE exercise_id = "
            "(SELECT id FROM exercises WHERE session_id = 'test-session-v2-001' AND number = 2)"
        )
        assert cur.fetchone()[0] == 0


def test_insert_session_is_idempotent(conn):
    insert_session(conn, make_session())
    insert_session(conn, make_session())

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sessions WHERE session_id = 'test-session-v2-001'")
        assert cur.fetchone()[0] == 1

        cur.execute("SELECT COUNT(*) FROM exercises WHERE session_id = 'test-session-v2-001'")
        assert cur.fetchone()[0] == 3
