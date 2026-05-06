import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from traininglogs.models.models_v2 import (
    ActivitySet,
    AnySet,
    DropSet,
    DropSetDetails,
    DropSetTechnique,
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
    StaticDetails,
    StaticTechnique,
    StrengthSet,
    TrainingSession,
    UnilateralReps,
    WarmupSet,
    WorkingSet,
)

OUTPUT_JSON_DIR = (
    Path(__file__).parent.parent
    / "output_training_logs_json"
    / "BODYBUILDING TRANSFORMATION SYSTEM"
)


# --- RepCount ---

def test_rep_count_basic():
    rc = RepCount(full=10, partial=2)
    assert rc.total_reps == 12


def test_rep_count_partial_none_coerced():
    rc = RepCount.model_validate({"full": 8, "partial": None})
    assert rc.partial == 0


def test_rep_count_negative_full_raises():
    with pytest.raises(ValidationError):
        RepCount(full=-1)


def test_rep_count_model_dump_snake_case():
    d = RepCount(full=5, partial=1).model_dump()
    assert "full" in d and "partial" in d


# --- Rest ---

def test_rest_valid_minutes():
    r = Rest(minutes=5)
    assert r.minutes == 5
    assert r.seconds is None


def test_rest_valid_seconds():
    r = Rest(seconds=90)
    assert r.seconds == 90
    assert r.minutes is None


def test_rest_both_none_valid():
    r = Rest()
    assert r.minutes is None and r.seconds is None


def test_rest_both_set_raises():
    with pytest.raises(ValidationError):
        Rest(minutes=2, seconds=90)


def test_rest_minutes_too_high_raises():
    with pytest.raises(ValidationError):
        Rest(minutes=16)


def test_rest_minutes_negative_raises():
    with pytest.raises(ValidationError):
        Rest(minutes=-1)


def test_rest_seconds_too_high_raises():
    with pytest.raises(ValidationError):
        Rest(seconds=901)


def test_rest_seconds_negative_raises():
    with pytest.raises(ValidationError):
        Rest(seconds=-1)


def test_rest_minutes_zero_valid():
    r = Rest(minutes=0)
    assert r.minutes == 0


def test_rest_seconds_zero_valid():
    r = Rest(seconds=0)
    assert r.seconds == 0


# --- UnilateralReps ---

def test_unilateral_reps_valid():
    u = UnilateralReps(
        left=RepCount(full=8, partial=1),
        right=RepCount(full=8),
    )
    assert u.left.total_reps == 9
    assert u.right.total_reps == 8


def test_unilateral_reps_both_none_valid():
    u = UnilateralReps()
    assert u.left is None and u.right is None


def test_unilateral_reps_one_side_only():
    u = UnilateralReps(left=RepCount(full=6))
    assert u.left.full == 6
    assert u.right is None


# --- StrengthSet ---

def test_strength_set_basic():
    ss = StrengthSet(number=1, weight_kg=60.0, rep_count=RepCount(full=10))
    assert ss.set_type == "strength"
    assert ss.weight_kg == 60.0


def test_strength_set_bodyweight():
    ss = StrengthSet(number=1, weight_kg=None)
    assert ss.weight_kg is None


def test_strength_set_feel_set_no_rep_count():
    ss = StrengthSet(number=1, rep_count=None)
    assert ss.rep_count is None


def test_strength_set_negative_weight_raises():
    with pytest.raises(ValidationError):
        StrengthSet(number=1, weight_kg=-1.0)


def test_strength_set_rpe_half_step_accepted():
    ss = StrengthSet(number=1, rpe=7.5)
    assert ss.rpe == 7.5


def test_strength_set_rpe_out_of_range_raises():
    with pytest.raises(ValidationError):
        StrengthSet(number=1, rpe=11.0)


def test_strength_set_rpe_bad_fraction_raises():
    with pytest.raises(ValidationError):
        StrengthSet(number=1, rpe=7.3)


def test_strength_set_rest_minutes():
    ss = StrengthSet(number=1, rest=Rest(minutes=3))
    assert ss.rest.minutes == 3


def test_strength_set_with_unilateral():
    ss = StrengthSet(
        number=1,
        unilateral_rep_count=UnilateralReps(
            left=RepCount(full=8),
            right=RepCount(full=7, partial=1),
        ),
    )
    assert ss.unilateral_rep_count.left.full == 8
    assert ss.unilateral_rep_count.right.total_reps == 8


def test_strength_set_failure_technique_without_rpe_10_raises():
    with pytest.raises(ValidationError):
        StrengthSet(
            number=1,
            weight_kg=60.0,
            rep_count=RepCount(full=10),
            rpe=8.0,
            failure_technique=MyoRepsTechnique(
                technique_type="MyoReps",
                details=MyoRepDetails(
                    mini_sets=[MyoRep(number=1, rep_count=RepCount(full=4))]
                ),
            ),
        )


def test_strength_set_model_dump_no_camel_case():
    ss = StrengthSet(
        number=1,
        weight_kg=55.0,
        rep_count=RepCount(full=10, partial=2),
        rpe=8.0,
        rep_quality_assessment=RepQualityAssessment.GOOD,
    )
    d = ss.model_dump()
    for key in ("weightKg", "repCount", "repQuality", "actualRestMinutes", "failureTechnique"):
        assert key not in d, f"Unexpected camelCase key: {key}"
    assert "weight_kg" in d
    assert "rep_count" in d
    assert "rep_quality_assessment" in d


def test_strength_set_model_dump_mode_json_enum_as_string():
    ss = StrengthSet(
        number=1,
        weight_kg=55.0,
        rep_count=RepCount(full=10),
        rep_quality_assessment=RepQualityAssessment.PERFECT,
    )
    d = ss.model_dump(mode="json")
    assert d["rep_quality_assessment"] == "perfect"


def test_strength_set_rest_too_high_raises():
    with pytest.raises(ValidationError):
        StrengthSet(number=1, rest=Rest(minutes=20))


def test_strength_set_rest_negative_raises():
    with pytest.raises(ValidationError):
        StrengthSet(number=1, rest=Rest(minutes=-1))


# --- ActivitySet ---

def test_activity_set_basic():
    a = ActivitySet(number=1, duration_seconds=300)
    assert a.set_type == "activity"
    assert a.duration_seconds == 300


def test_activity_set_all_fields():
    a = ActivitySet(
        number=1,
        duration_seconds=40,
        distance_meters=40.0,
        heart_rate_bpm=165,
        rest=Rest(seconds=120),
    )
    assert a.distance_meters == 40.0
    assert a.heart_rate_bpm == 165
    assert a.rest.seconds == 120


def test_activity_set_all_optional_none():
    a = ActivitySet(number=1)
    assert a.duration_seconds is None
    assert a.distance_meters is None
    assert a.heart_rate_bpm is None


def test_activity_set_duration_zero_raises():
    with pytest.raises(ValidationError):
        ActivitySet(number=1, duration_seconds=0)


def test_activity_set_distance_negative_raises():
    with pytest.raises(ValidationError):
        ActivitySet(number=1, distance_meters=-1.0)


def test_activity_set_heart_rate_zero_raises():
    with pytest.raises(ValidationError):
        ActivitySet(number=1, heart_rate_bpm=0)


def test_activity_set_rest_seconds():
    a = ActivitySet(number=1, rest=Rest(seconds=90))
    assert a.rest.seconds == 90


# --- AnySet discriminator dispatch ---

def test_anyset_dispatches_to_strength_set():
    from pydantic import TypeAdapter
    ta = TypeAdapter(AnySet)
    s = ta.validate_python({"set_type": "strength", "number": 1, "weight_kg": 80.0})
    assert isinstance(s, StrengthSet)


def test_anyset_dispatches_to_activity_set():
    from pydantic import TypeAdapter
    ta = TypeAdapter(AnySet)
    a = ta.validate_python({"set_type": "activity", "number": 1, "duration_seconds": 60})
    assert isinstance(a, ActivitySet)


def test_anyset_invalid_type_raises():
    from pydantic import TypeAdapter
    ta = TypeAdapter(AnySet)
    with pytest.raises(ValidationError):
        ta.validate_python({"set_type": "unknown", "number": 1})


# --- Goal ---

def test_goal_rest_too_high_raises():
    with pytest.raises(ValidationError):
        Goal(rest=Rest(minutes=20))


def test_goal_rest_negative_raises():
    with pytest.raises(ValidationError):
        Goal(rest=Rest(minutes=-1))


def test_goal_rest_none_accepted():
    g = Goal(weight_kg=50.0, sets=3, rep_range=RepRange(min=8, max=12), rest=None)
    assert g.rest is None


def test_goal_all_optional_none():
    g = Goal()
    assert g.weight_kg is None
    assert g.sets is None
    assert g.rep_range is None
    assert g.rest is None
    assert g.distance_meters is None
    assert g.target_duration_seconds is None


def test_goal_activity_fields():
    g = Goal(distance_meters=40.0, target_duration_seconds=5)
    assert g.distance_meters == 40.0
    assert g.target_duration_seconds == 5


def test_goal_sets_zero_raises():
    with pytest.raises(ValidationError):
        Goal(sets=0)


def test_goal_weight_negative_raises():
    with pytest.raises(ValidationError):
        Goal(weight_kg=-1.0)


def test_goal_distance_negative_raises():
    with pytest.raises(ValidationError):
        Goal(distance_meters=-5.0)


def test_goal_target_duration_zero_raises():
    with pytest.raises(ValidationError):
        Goal(target_duration_seconds=0)


def test_goal_rest_seconds_accepted():
    g = Goal(rest=Rest(seconds=45))
    assert g.rest.seconds == 45


# --- Failure technique discriminated union dispatch ---

def test_failure_technique_myoreps_dispatch():
    data = {
        "technique_type": "MyoReps",
        "details": {
            "mini_sets": [
                {"number": 1, "rep_count": {"full": 4, "partial": 0}},
                {"number": 2, "rep_count": {"full": 3, "partial": 0}},
            ]
        },
    }
    ft = MyoRepsTechnique.model_validate(data)
    assert ft.technique_type == "MyoReps"
    assert len(ft.details.mini_sets) == 2


def test_failure_technique_llp_dispatch():
    data = {"technique_type": "LLP", "details": {"partial_rep_count": 5}}
    ft = LLPTechnique.model_validate(data)
    assert ft.details.partial_rep_count == 5


def test_failure_technique_static_dispatch():
    data = {"technique_type": "StaticHold", "details": {"hold_duration_seconds": 10}}
    ft = StaticTechnique.model_validate(data)
    assert ft.details.hold_duration_seconds == 10


def test_failure_technique_dropset_dispatch():
    data = {
        "technique_type": "DropSet",
        "details": {
            "drop_sets": [
                {"number": 1, "weight_kg": 40.0, "rep_count": {"full": 8, "partial": 0}},
            ]
        },
    }
    ft = DropSetTechnique.model_validate(data)
    assert len(ft.details.drop_sets) == 1


# --- WarmupSet null filtering ---

def test_warmup_set_null_entries_filtered():
    ex = Exercise.model_validate(
        {
            "number": 1,
            "name": "Lat Pulldown",
            "warmup_sets": [
                {"number": 1, "weight_kg": 40.0, "rep_count": 6},
                None,
            ],
        }
    )
    assert len(ex.warmup_sets) == 1


# --- Sequential exercise numbering ---

def test_training_session_non_sequential_exercises_raises():
    with pytest.raises(ValidationError):
        TrainingSession(
            data_model_version="0.0.1",
            data_model_type="TrainingSession",
            session_id="test-001",
            user_id="7",
            user_name="Test User",
            date="2026-01-01",
            exercises=[
                Exercise(number=1, name="Bench Press"),
                Exercise(number=3, name="Overhead Press"),  # skipped 2
            ],
        )


# --- Ad-hoc session (no program / phase / week / focus) ---

def test_training_session_adhoc_no_program_fields():
    s = TrainingSession(
        data_model_version="2.0.0",
        data_model_type="TrainingSession",
        session_id="adhoc-001",
        user_id="7",
        user_name="Test User",
        date="2026-05-06",
        exercises=[Exercise(number=1, name="Pull-up")],
    )
    assert s.program is None
    assert s.phase is None
    assert s.week is None
    assert s.focus is None
    assert s.session_duration_minutes is None


def test_training_session_weight_unit_default_kg():
    s = TrainingSession(
        data_model_version="2.0.0",
        data_model_type="TrainingSession",
        session_id="test-002",
        user_id="7",
        user_name="Test User",
        date="2026-05-06",
        exercises=[],
    )
    assert s.weight_unit == "kg"


def test_training_session_weight_unit_lbs():
    s = TrainingSession(
        data_model_version="2.0.0",
        data_model_type="TrainingSession",
        session_id="test-003",
        user_id="7",
        user_name="Test User",
        date="2026-05-06",
        exercises=[],
        weight_unit="lbs",
    )
    assert s.weight_unit == "lbs"


def test_training_session_program_empty_string_raises():
    with pytest.raises(ValidationError):
        TrainingSession(
            data_model_version="2.0.0",
            data_model_type="TrainingSession",
            session_id="test-004",
            user_id="7",
            user_name="Test User",
            date="2026-05-06",
            exercises=[],
            program="   ",
        )


def test_training_session_week_out_of_range_raises():
    with pytest.raises(ValidationError):
        TrainingSession(
            data_model_version="2.0.0",
            data_model_type="TrainingSession",
            session_id="test-005",
            user_id="7",
            user_name="Test User",
            date="2026-05-06",
            exercises=[],
            program="Test",
            program_length_weeks=12,
            week=13,
        )


def test_training_session_week_without_program_length_no_error():
    s = TrainingSession(
        data_model_version="2.0.0",
        data_model_type="TrainingSession",
        session_id="test-006",
        user_id="7",
        user_name="Test User",
        date="2026-05-06",
        exercises=[],
        week=5,
    )
    assert s.week == 5


# --- Round-trip from real JSON on disk ---

def test_training_session_round_trip_from_json_file():
    json_files = list(OUTPUT_JSON_DIR.rglob("*.json"))
    assert json_files, "No JSON files found for round-trip test"

    sample = json_files[0]
    raw = json.loads(sample.read_text())
    session = TrainingSession.model_validate(raw)

    dumped = session.model_dump(mode="json")
    assert dumped["session_id"] == raw["session_id"]
    assert dumped["date"] == raw["date"]
    assert len(dumped["exercises"]) == len(raw["exercises"])


def test_training_session_round_trip_preserves_failure_technique():
    json_files = list(OUTPUT_JSON_DIR.rglob("*.json"))
    for path in json_files:
        raw = json.loads(path.read_text())
        session = TrainingSession.model_validate(raw)
        dumped = session.model_dump(mode="json")
        for ex_raw, ex_dumped in zip(raw["exercises"], dumped["exercises"]):
            for ws_raw, ws_dumped in zip(
                ex_raw.get("working_sets") or [],
                ex_dumped.get("sets") or [],
            ):
                has_ft_raw = ws_raw.get("failure_technique") is not None
                has_ft_dumped = ws_dumped.get("failure_technique") is not None
                assert has_ft_raw == has_ft_dumped, (
                    f"failure_technique presence mismatch in {path.name}"
                )
