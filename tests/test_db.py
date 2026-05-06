import json
import os

import pytest

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.insert import insert_session
from traininglogs.models.models import (
    ActivitySet,
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
    Rest,
    StrengthSet,
    TrainingSession,
    UnilateralReps,
    WarmupSet,
)

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)


def make_session(session_id: str = "test-session-v2-001") -> TrainingSession:
    return TrainingSession(
        data_model_version="2.0.0",
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
        weight_unit="kg",
        exercises=[
            Exercise(
                number=1,
                name="Lat Pulldown",
                exercise_type="strength",
                notes="felt strong",
                warmup_notes="Pyramid",
                form_cues=["lean back 15 degrees", "squeeze lats"],
                current_goal=Goal(
                    weight_kg=55.0,
                    sets=3,
                    rep_range=RepRange(min=10, max=12),
                    rest=Rest(minutes=2),
                ),
                warmup_sets=[
                    WarmupSet(number=1, weight_kg=40.0, rep_count=6),
                ],
                sets=[
                    StrengthSet(
                        number=1,
                        weight_kg=55.0,
                        rep_count=RepCount(full=12, partial=0),
                        rpe=8.0,
                        rep_quality_assessment=RepQualityAssessment.GOOD,
                    ),
                    StrengthSet(
                        number=2,
                        weight_kg=55.0,
                        rep_count=RepCount(full=10, partial=2),
                        rpe=10.0,
                        rep_quality_assessment=RepQualityAssessment.PERFECT,
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
                exercise_type="strength",
                warmup_notes="Pyramid",
                form_cues=["sit upright", "squeeze shoulder blades"],
                current_goal=Goal(
                    weight_kg=50.0,
                    sets=3,
                    rep_range=RepRange(min=12, max=15),
                    rest=Rest(minutes=2),
                ),
                sets=[
                    StrengthSet(
                        number=1,
                        weight_kg=50.0,
                        rep_count=RepCount(full=14, partial=0),
                        rpe=9.0,
                        rep_quality_assessment=RepQualityAssessment.GOOD,
                    ),
                    StrengthSet(
                        number=2,
                        weight_kg=50.0,
                        rep_count=RepCount(full=12, partial=0),
                        rpe=10.0,
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
                exercise_type="strength",
                sets=[
                    StrengthSet(
                        number=1,
                        weight_kg=20.0,
                        rep_count=RepCount(full=15, partial=0),
                    ),
                ],
            ),
        ],
    )


def make_session_with_activity(session_id: str = "test-session-activity-001") -> TrainingSession:
    return TrainingSession(
        data_model_version="2.0.0",
        data_model_type="TrainingSession",
        session_id=session_id,
        user_id="7",
        user_name="Apoorva Sharma",
        date="2026-01-02",
        exercises=[
            Exercise(
                number=1,
                name="Incline Walk",
                exercise_type="activity",
                current_goal=Goal(distance_meters=1000.0, target_duration_seconds=600),
                sets=[
                    ActivitySet(
                        number=1,
                        duration_seconds=620,
                        distance_meters=1020.0,
                        heart_rate_bpm=138,
                        rest=Rest(seconds=60),
                    ),
                ],
            ),
        ],
    )


def make_session_with_unilateral(session_id: str = "test-session-uni-001") -> TrainingSession:
    return TrainingSession(
        data_model_version="2.0.0",
        data_model_type="TrainingSession",
        session_id=session_id,
        user_id="7",
        user_name="Apoorva Sharma",
        date="2026-01-03",
        exercises=[
            Exercise(
                number=1,
                name="Single Arm Row",
                sets=[
                    StrengthSet(
                        number=1,
                        weight_kg=30.0,
                        unilateral_rep_count=UnilateralReps(
                            left=RepCount(full=10, partial=1),
                            right=RepCount(full=10),
                        ),
                        rpe=8.0,
                    ),
                ],
            ),
        ],
    )


def make_session_lbs(session_id: str = "test-session-lbs-001") -> TrainingSession:
    return TrainingSession(
        data_model_version="2.0.0",
        data_model_type="TrainingSession",
        session_id=session_id,
        user_id="7",
        user_name="Apoorva Sharma",
        date="2026-01-04",
        weight_unit="lbs",
        exercises=[
            Exercise(
                number=1,
                name="Bench Press",
                sets=[StrengthSet(number=1, weight_kg=100.0, rep_count=RepCount(full=5))],
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
    conn.rollback()
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
            "SELECT date, phase, week, focus, duration_minutes, weight_unit, user_id, user_name "
            "FROM sessions WHERE session_id = 'test-session-v2-001'"
        )
        row = cur.fetchone()

    assert str(row[0]) == "2026-01-01"
    assert row[1] == 1
    assert row[2] == 1
    assert row[3] == "Pull Hypertrophy"
    assert row[4] == 90
    assert row[5] == "kg"
    assert row[6] == "7"
    assert row[7] == "Apoorva Sharma"


def test_insert_session_weight_unit_lbs(conn):
    insert_session(conn, make_session_lbs())

    with conn.cursor() as cur:
        cur.execute("SELECT weight_unit FROM sessions WHERE session_id = 'test-session-lbs-001'")
        assert cur.fetchone()[0] == "lbs"


def test_insert_exercise_with_goal(conn):
    insert_session(conn, make_session())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT goal_weight_kg, goal_sets, goal_rep_min, goal_rep_max, "
            "goal_rest_min, goal_rest_seconds, exercise_type, form_cues "
            "FROM exercises WHERE session_id = 'test-session-v2-001' AND number = 1"
        )
        row = cur.fetchone()

    assert float(row[0]) == 55.0
    assert row[1] == 3
    assert row[2] == 10
    assert row[3] == 12
    assert row[4] == 2       # rest.minutes
    assert row[5] is None    # rest.seconds
    assert row[6] == "strength"
    assert row[7] == ["lean back 15 degrees", "squeeze lats"]


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


def test_insert_exercise_activity_type_and_goal(conn):
    insert_session(conn, make_session_with_activity())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT exercise_type, goal_distance_meters, goal_target_duration_sec "
            "FROM exercises WHERE session_id = 'test-session-activity-001' AND number = 1"
        )
        row = cur.fetchone()

    assert row[0] == "activity"
    assert float(row[1]) == 1000.0
    assert row[2] == 600


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


def test_insert_working_set_set_type_strength(conn):
    insert_session(conn, make_session())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT set_type FROM working_sets WHERE exercise_id = "
            "(SELECT id FROM exercises WHERE session_id = 'test-session-v2-001' AND number = 1) "
            "AND number = 1"
        )
        assert cur.fetchone()[0] == "strength"


def test_insert_working_set_activity_fields(conn):
    insert_session(conn, make_session_with_activity())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT set_type, duration_seconds, distance_meters, heart_rate_bpm, rest_seconds "
            "FROM working_sets WHERE exercise_id = "
            "(SELECT id FROM exercises WHERE session_id = 'test-session-activity-001' AND number = 1)"
        )
        row = cur.fetchone()

    assert row[0] == "activity"
    assert row[1] == 620
    assert float(row[2]) == 1020.0
    assert row[3] == 138
    assert row[4] == 60


def test_insert_working_set_unilateral_reps(conn):
    insert_session(conn, make_session_with_unilateral())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT left_reps_full, left_reps_partial, right_reps_full, right_reps_partial "
            "FROM working_sets WHERE exercise_id = "
            "(SELECT id FROM exercises WHERE session_id = 'test-session-uni-001' AND number = 1)"
        )
        row = cur.fetchone()

    assert row[0] == 10
    assert row[1] == 1
    assert row[2] == 10
    assert row[3] == 0


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
