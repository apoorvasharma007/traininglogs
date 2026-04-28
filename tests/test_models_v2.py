import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from traininglogs.models.models_v2 import (
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
    StaticDetails,
    StaticTechnique,
    TrainingSession,
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


# --- Goal rest_minutes validation bug fix ---

def test_goal_rest_too_high_raises():
    with pytest.raises(ValidationError):
        Goal(weight_kg=50.0, sets=3, rep_range=RepRange(min=8, max=12), rest_minutes=20)


def test_goal_rest_negative_raises():
    with pytest.raises(ValidationError):
        Goal(weight_kg=50.0, sets=3, rep_range=RepRange(min=8, max=12), rest_minutes=-1)


def test_goal_rest_none_accepted():
    g = Goal(weight_kg=50.0, sets=3, rep_range=RepRange(min=8, max=12), rest_minutes=None)
    assert g.rest_minutes is None


# --- WorkingSet rest_minutes validation bug fix ---

def test_working_set_rest_too_high_raises():
    with pytest.raises(ValidationError):
        WorkingSet(
            number=1,
            weight_kg=60.0,
            rep_count=RepCount(full=10),
            actual_rest_minutes=20,
        )


def test_working_set_rest_negative_raises():
    with pytest.raises(ValidationError):
        WorkingSet(
            number=1,
            weight_kg=60.0,
            rep_count=RepCount(full=10),
            actual_rest_minutes=-1,
        )


# --- RPE validation ---

def test_rpe_half_step_accepted():
    ws = WorkingSet(number=1, weight_kg=50.0, rep_count=RepCount(full=10), rpe=7.5)
    assert ws.rpe == 7.5


def test_rpe_out_of_range_raises():
    with pytest.raises(ValidationError):
        WorkingSet(number=1, weight_kg=50.0, rep_count=RepCount(full=10), rpe=11.0)


def test_rpe_bad_fraction_raises():
    with pytest.raises(ValidationError):
        WorkingSet(number=1, weight_kg=50.0, rep_count=RepCount(full=10), rpe=7.3)


# --- Failure technique requires RPE 10 ---

def test_failure_technique_without_rpe_10_raises():
    with pytest.raises(ValidationError):
        WorkingSet(
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


# --- Discriminated union dispatch ---

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


# --- model_dump is snake_case, no camelCase ---

def test_working_set_model_dump_no_camel_case():
    ws = WorkingSet(
        number=1,
        weight_kg=55.0,
        rep_count=RepCount(full=10, partial=2),
        rpe=8.0,
        rep_quality_assessment=RepQualityAssessment.GOOD,
    )
    d = ws.model_dump()
    # None of the old camelCase keys should appear
    for key in ("weightKg", "repCount", "repQuality", "actualRestMinutes", "failureTechnique"):
        assert key not in d, f"Unexpected camelCase key: {key}"
    assert "weight_kg" in d
    assert "rep_count" in d
    assert "rep_quality_assessment" in d


def test_model_dump_mode_json_enum_as_string():
    ws = WorkingSet(
        number=1,
        weight_kg=55.0,
        rep_count=RepCount(full=10),
        rep_quality_assessment=RepQualityAssessment.PERFECT,
    )
    d = ws.model_dump(mode="json")
    assert d["rep_quality_assessment"] == "perfect"


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
            program="Test",
            program_author="Test",
            program_length_weeks=12,
            phase=1,
            week=1,
            is_deload_week=False,
            focus="Push",
            exercises=[
                Exercise(number=1, name="Bench Press"),
                Exercise(number=3, name="Overhead Press"),  # skipped 2
            ],
            session_duration_minutes=60,
        )


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
                ex_dumped.get("working_sets") or [],
            ):
                has_ft_raw = ws_raw.get("failure_technique") is not None
                has_ft_dumped = ws_dumped.get("failure_technique") is not None
                assert has_ft_raw == has_ft_dumped, (
                    f"failure_technique presence mismatch in {path.name}"
                )
