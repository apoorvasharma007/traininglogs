from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from traininglogs.models.models import (
    DropSetDetails,
    DropSetTechnique,
    Exercise,
    FailureTechnique,
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
    SessionCooldown,
    SessionWarmup,
    StaticDetails,
    StaticTechnique,
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


# ---------------------------------------------------------------------------
# RepCount
# ---------------------------------------------------------------------------

class TestRepCount:
    def test_total_reps_is_sum_of_full_and_partial(self) -> None:
        assert RepCount(full=8, partial=2).total_reps == 10

    def test_partial_defaults_to_zero(self) -> None:
        assert RepCount(full=5).partial == 0

    def test_partial_none_coerced_to_zero(self) -> None:
        assert RepCount.model_validate({"full": 8, "partial": None}).partial == 0

    @pytest.mark.parametrize("full", [-1, -100])
    def test_negative_full_rejected(self, full: int) -> None:
        with pytest.raises(ValidationError):
            RepCount(full=full)

    @pytest.mark.parametrize("partial", [-1, -50])
    def test_negative_partial_rejected(self, partial: int) -> None:
        with pytest.raises(ValidationError):
            RepCount(full=5, partial=partial)

    def test_zero_full_is_valid(self) -> None:
        assert RepCount(full=0).total_reps == 0


# ---------------------------------------------------------------------------
# Rest
# ---------------------------------------------------------------------------

class TestRest:
    def test_minutes_and_seconds_are_mutually_exclusive(self) -> None:
        with pytest.raises(ValidationError):
            Rest(minutes=2, seconds=90)

    def test_both_none_is_valid(self) -> None:
        r = Rest()
        assert r.minutes is None and r.seconds is None

    @pytest.mark.parametrize("minutes", [-1, 16, 100])
    def test_minutes_out_of_range_rejected(self, minutes: int) -> None:
        with pytest.raises(ValidationError):
            Rest(minutes=minutes)

    @pytest.mark.parametrize("seconds", [-1, 901, 9999])
    def test_seconds_out_of_range_rejected(self, seconds: int) -> None:
        with pytest.raises(ValidationError):
            Rest(seconds=seconds)

    @pytest.mark.parametrize("minutes", [0, 1, 15])
    def test_minutes_boundary_values_accepted(self, minutes: int) -> None:
        assert Rest(minutes=minutes).minutes == minutes

    @pytest.mark.parametrize("seconds", [0, 1, 900])
    def test_seconds_boundary_values_accepted(self, seconds: int) -> None:
        assert Rest(seconds=seconds).seconds == seconds


# ---------------------------------------------------------------------------
# WorkingSet — flat model replacing StrengthSet + ActivitySet
# ---------------------------------------------------------------------------

class TestWorkingSet:
    def test_all_measurement_fields_are_optional(self) -> None:
        ws = WorkingSet(number=1)
        assert ws.weight_kg is None
        assert ws.rep_count is None
        assert ws.duration_seconds is None
        assert ws.distance_meters is None
        assert ws.heart_rate_bpm is None
        assert ws.failure_technique is None

    def test_strength_fields_accepted(self) -> None:
        ws = WorkingSet(
            number=1,
            weight_kg=100.0,
            rep_count=RepCount(full=5),
            rpe=8.0,
            rep_quality_assessment=RepQualityAssessment.PERFECT,
        )
        assert ws.weight_kg == 100.0
        assert ws.rep_count.total_reps == 5
        assert ws.rpe == 8.0

    def test_activity_fields_accepted(self) -> None:
        ws = WorkingSet(number=1, duration_seconds=1800, distance_meters=5000.0, heart_rate_bpm=155)
        assert ws.duration_seconds == 1800
        assert ws.distance_meters == 5000.0
        assert ws.heart_rate_bpm == 155

    def test_mixed_strength_and_activity_fields_valid(self) -> None:
        ws = WorkingSet(number=1, weight_kg=60.0, duration_seconds=60)
        assert ws.weight_kg == 60.0
        assert ws.duration_seconds == 60

    def test_no_set_type_field_in_output(self) -> None:
        ws = WorkingSet(number=1, weight_kg=80.0, rep_count=RepCount(full=8))
        assert "set_type" not in ws.model_dump()

    def test_rep_quality_serialises_as_string(self) -> None:
        ws = WorkingSet(number=1, rep_quality_assessment=RepQualityAssessment.GOOD)
        assert ws.model_dump(mode="json")["rep_quality_assessment"] == "good"

    def test_unilateral_reps_stored_correctly(self) -> None:
        ws = WorkingSet(
            number=1,
            unilateral_rep_count=UnilateralReps(
                left=RepCount(full=8), right=RepCount(full=7, partial=1)
            ),
        )
        assert ws.unilateral_rep_count.left.full == 8
        assert ws.unilateral_rep_count.right.total_reps == 8

    def test_failure_technique_without_rpe_10_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Failure technique can only be used with RPE 10"):
            WorkingSet(
                number=1,
                weight_kg=80.0,
                rep_count=RepCount(full=8),
                rpe=9.0,
                failure_technique=LLPTechnique(
                    technique_type="LLP", details=LLPDetails(partial_rep_count=5)
                ),
            )

    def test_failure_technique_with_no_rpe_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkingSet(
                number=1,
                failure_technique=MyoRepsTechnique(
                    technique_type="MyoReps",
                    details=MyoRepDetails(mini_sets=[MyoRep(number=1, rep_count=RepCount(full=4))]),
                ),
            )

    def test_failure_technique_at_rpe_10_accepted(self) -> None:
        ws = WorkingSet(
            number=1,
            weight_kg=80.0,
            rpe=10.0,
            failure_technique=LLPTechnique(
                technique_type="LLP", details=LLPDetails(partial_rep_count=3)
            ),
        )
        assert ws.failure_technique.technique_type == "LLP"

    @pytest.mark.parametrize("rpe", [0.0, 0.5, 10.5, 11.0, -1.0])
    def test_rpe_out_of_range_rejected(self, rpe: float) -> None:
        with pytest.raises(ValidationError):
            WorkingSet(number=1, rpe=rpe)

    @pytest.mark.parametrize("rpe", [1.0, 5.0, 7.5, 8.5, 10.0])
    def test_rpe_valid_values_accepted(self, rpe: float) -> None:
        assert WorkingSet(number=1, rpe=rpe).rpe == rpe

    def test_rpe_non_half_step_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkingSet(number=1, rpe=7.3)

    def test_negative_weight_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkingSet(number=1, weight_kg=-0.1)

    def test_zero_weight_accepted(self) -> None:
        assert WorkingSet(number=1, weight_kg=0.0).weight_kg == 0.0

    @pytest.mark.parametrize("duration", [0, -1])
    def test_non_positive_duration_rejected(self, duration: int) -> None:
        with pytest.raises(ValidationError):
            WorkingSet(number=1, duration_seconds=duration)

    def test_negative_distance_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkingSet(number=1, distance_meters=-1.0)

    @pytest.mark.parametrize("bpm", [0, -1])
    def test_non_positive_heart_rate_rejected(self, bpm: int) -> None:
        with pytest.raises(ValidationError):
            WorkingSet(number=1, heart_rate_bpm=bpm)

    def test_number_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkingSet(number=0)


# ---------------------------------------------------------------------------
# Failure technique discriminated union
# ---------------------------------------------------------------------------

class TestFailureTechniques:
    def test_myo_reps_dispatches_correctly(self) -> None:
        ft = MyoRepsTechnique.model_validate({
            "technique_type": "MyoReps",
            "details": {
                "mini_sets": [
                    {"number": 1, "rep_count": {"full": 4, "partial": 0}},
                    {"number": 2, "rep_count": {"full": 3, "partial": 0}},
                ]
            },
        })
        assert ft.technique_type == "MyoReps"
        assert len(ft.details.mini_sets) == 2

    def test_llp_dispatches_correctly(self) -> None:
        ft = LLPTechnique.model_validate(
            {"technique_type": "LLP", "details": {"partial_rep_count": 5}}
        )
        assert ft.details.partial_rep_count == 5

    def test_static_hold_dispatches_correctly(self) -> None:
        ft = StaticTechnique.model_validate(
            {"technique_type": "StaticHold", "details": {"hold_duration_seconds": 10}}
        )
        assert ft.details.hold_duration_seconds == 10

    def test_drop_set_dispatches_correctly(self) -> None:
        ft = DropSetTechnique.model_validate({
            "technique_type": "DropSet",
            "details": {
                "drop_sets": [
                    {"number": 1, "weight_kg": 40.0, "rep_count": {"full": 8, "partial": 0}}
                ]
            },
        })
        assert len(ft.details.drop_sets) == 1

    def test_llp_negative_partial_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LLPTechnique.model_validate(
                {"technique_type": "LLP", "details": {"partial_rep_count": -1}}
            )

    def test_static_zero_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StaticTechnique.model_validate(
                {"technique_type": "StaticHold", "details": {"hold_duration_seconds": 0}}
            )


# ---------------------------------------------------------------------------
# Goal
# ---------------------------------------------------------------------------

class TestGoal:
    def test_all_fields_optional(self) -> None:
        g = Goal()
        assert all(
            v is None
            for v in [g.weight_kg, g.sets, g.rep_range, g.rest, g.distance_meters, g.target_duration_seconds]
        )

    def test_rep_range_min_greater_than_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Goal(rep_range=RepRange(min=12, max=8))

    def test_zero_sets_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Goal(sets=0)

    def test_negative_weight_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Goal(weight_kg=-1.0)

    def test_rest_too_high_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Goal(rest=Rest(minutes=16))


# ---------------------------------------------------------------------------
# Exercise
# ---------------------------------------------------------------------------

class TestExercise:
    def test_exercise_type_field_absent_from_model(self) -> None:
        ex = Exercise(number=1, name="Bench Press")
        assert "exercise_type" not in ex.model_dump()

    def test_tags_is_a_list_and_accepts_multiple_values(self) -> None:
        ex = Exercise(number=1, name="Bench Press", tags=["absolute_strength", "muscle_growth"])
        assert ex.tags == ["absolute_strength", "muscle_growth"]

    def test_movement_pattern_accepts_multiple_values(self) -> None:
        ex = Exercise(number=1, name="Trap Bar Deadlift", movement_pattern=["squat", "hip_hinge"])
        assert set(ex.movement_pattern) == {"squat", "hip_hinge"}

    def test_all_classification_fields_optional(self) -> None:
        ex = Exercise(number=1, name="Plank")
        assert ex.tags is None
        assert ex.modality is None
        assert ex.movement_pattern is None

    def test_null_warmup_sets_filtered(self) -> None:
        ex = Exercise.model_validate({
            "number": 1,
            "name": "Squat",
            "warmup_sets": [{"number": 1, "weight_kg": 60.0, "rep_count": 5}, None],
        })
        assert len(ex.warmup_sets) == 1

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Exercise(number=1, name="   ")

    def test_zero_number_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Exercise(number=0, name="Squat")

    def test_sets_is_list_of_working_sets(self) -> None:
        ex = Exercise(
            number=1,
            name="Bench Press",
            tags=["absolute_strength"],
            modality="barbell",
            movement_pattern=["push"],
            sets=[
                WorkingSet(number=1, weight_kg=90.0, rep_count=RepCount(full=5), rpe=8.0),
                WorkingSet(number=2, weight_kg=90.0, rep_count=RepCount(full=5), rpe=8.5),
            ],
        )
        assert len(ex.sets) == 2
        assert "set_type" not in ex.model_dump(mode="json")["sets"][0]


# ---------------------------------------------------------------------------
# SessionWarmup and SessionCooldown
# ---------------------------------------------------------------------------

class TestSessionWarmup:
    def test_name_and_number_are_required(self) -> None:
        w = SessionWarmup(number=1, name="Ankle Rotation")
        assert w.number == 1 and w.name == "Ankle Rotation"

    def test_all_measurement_fields_optional(self) -> None:
        w = SessionWarmup(number=1, name="Leg Swings")
        assert w.reps is None and w.duration_seconds is None and w.notes is None

    def test_reps_and_duration_accepted_together(self) -> None:
        w = SessionWarmup(number=1, name="Neck Curls", reps=10, duration_seconds=4)
        assert w.reps == 10 and w.duration_seconds == 4

    @pytest.mark.parametrize("reps", [0, -1])
    def test_non_positive_reps_rejected(self, reps: int) -> None:
        with pytest.raises(ValidationError):
            SessionWarmup(number=1, name="Circles", reps=reps)

    @pytest.mark.parametrize("duration", [0, -1])
    def test_non_positive_duration_rejected(self, duration: int) -> None:
        with pytest.raises(ValidationError):
            SessionWarmup(number=1, name="Hold", duration_seconds=duration)

    def test_zero_number_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SessionWarmup(number=0, name="Ankle Rotation")

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SessionWarmup(number=1, name="  ")


class TestSessionCooldown:
    def test_name_and_number_are_required(self) -> None:
        c = SessionCooldown(number=1, name="Cobra Stretch")
        assert c.number == 1 and c.name == "Cobra Stretch"

    def test_duration_accepted(self) -> None:
        assert SessionCooldown(number=1, name="Cobra Stretch", duration_seconds=30).duration_seconds == 30

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SessionCooldown(number=1, name="")

    def test_zero_number_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SessionCooldown(number=0, name="Stretch")


# ---------------------------------------------------------------------------
# TrainingSession
# ---------------------------------------------------------------------------

class TestTrainingSession:
    def _make(self, **overrides) -> dict:
        base = {
            "data_model_version": "3.0.0",
            "data_model_type": "TrainingSession",
            "session_id": "test-001",
            "user_id": "7",
            "user_name": "Apoorva",
            "date": "2026-05-13",
            "exercises": [Exercise(number=1, name="Squat")],
        }
        base.update(overrides)
        return base

    def test_exercises_sequential_numbering_enforced(self) -> None:
        with pytest.raises(ValidationError, match="sequential"):
            TrainingSession(**self._make(exercises=[
                Exercise(number=1, name="Squat"),
                Exercise(number=3, name="Bench Press"),
            ]))

    def test_warmup_sequential_numbering_enforced(self) -> None:
        with pytest.raises(ValidationError, match="sequential"):
            TrainingSession(**self._make(warmup=[
                SessionWarmup(number=1, name="Ankle Rotation"),
                SessionWarmup(number=3, name="Leg Swings"),
            ]))

    def test_cooldown_sequential_numbering_enforced(self) -> None:
        with pytest.raises(ValidationError, match="sequential"):
            TrainingSession(**self._make(cooldown=[
                SessionCooldown(number=1, name="Cobra Stretch"),
                SessionCooldown(number=5, name="Quad Stretch"),
            ]))

    def test_warmup_and_cooldown_number_independently_of_exercises(self) -> None:
        s = TrainingSession(**self._make(
            warmup=[SessionWarmup(number=1, name="A"), SessionWarmup(number=2, name="B")],
            exercises=[Exercise(number=1, name="Squat"), Exercise(number=2, name="Bench")],
            cooldown=[SessionCooldown(number=1, name="X"), SessionCooldown(number=2, name="Y")],
        ))
        assert len(s.warmup) == 2
        assert len(s.exercises) == 2
        assert len(s.cooldown) == 2

    def test_warmup_and_cooldown_default_to_none(self) -> None:
        s = TrainingSession(**self._make())
        assert s.warmup is None and s.cooldown is None

    def test_week_exceeds_program_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrainingSession(**self._make(program="Test", program_length_weeks=12, week=13))

    def test_week_within_program_length_accepted(self) -> None:
        s = TrainingSession(**self._make(program="Test", program_length_weeks=12, week=12))
        assert s.week == 12

    def test_week_without_program_length_accepted(self) -> None:
        assert TrainingSession(**self._make(week=5)).week == 5

    def test_whitespace_program_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrainingSession(**self._make(program="   "))

    def test_weight_unit_defaults_to_kg(self) -> None:
        assert TrainingSession(**self._make()).weight_unit == "kg"

    def test_notes_defaults_to_none(self) -> None:
        assert TrainingSession(**self._make()).notes is None

    def test_notes_accepted(self) -> None:
        s = TrainingSession(**self._make(notes="Legs are sore, warmup ran long."))
        assert s.notes == "Legs are sore, warmup ran long."

    def test_get_exercise_by_name_case_insensitive(self) -> None:
        s = TrainingSession(**self._make(exercises=[
            Exercise(number=1, name="Bench Press"),
            Exercise(number=2, name="Squat"),
        ]))
        assert s.get_exercise_by_name("bench press") is not None
        assert s.get_exercise_by_name("SQUAT") is not None
        assert s.get_exercise_by_name("Deadlift") is None

    @pytest.mark.parametrize("field", ["session_id", "user_id", "user_name", "data_model_version"])
    def test_required_string_fields_reject_empty_string(self, field: str) -> None:
        with pytest.raises(ValidationError):
            TrainingSession(**self._make(**{field: ""}))


# ---------------------------------------------------------------------------
# Round-trip: historical JSON must still load against the new model
# (old JSON carries exercise_type and set_type as extra fields; Pydantic ignores them)
# ---------------------------------------------------------------------------

class TestRoundTrip:
    @pytest.fixture(autouse=True)
    def require_json_files(self) -> None:
        if not list(OUTPUT_JSON_DIR.rglob("*.json")):
            pytest.skip("No historical JSON files available")

    def test_all_historical_sessions_load_without_error(self) -> None:
        errors = []
        for path in OUTPUT_JSON_DIR.rglob("*.json"):
            try:
                raw = json.loads(path.read_text())
                TrainingSession.model_validate(raw)
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
        assert not errors, "\n".join(errors)

    def test_session_identity_fields_survive_round_trip(self) -> None:
        sample = next(OUTPUT_JSON_DIR.rglob("*.json"))
        raw = json.loads(sample.read_text())
        dumped = TrainingSession.model_validate(raw).model_dump(mode="json")
        assert dumped["session_id"] == raw["session_id"]
        assert dumped["date"] == raw["date"]
        assert len(dumped["exercises"]) == len(raw["exercises"])

    def test_failure_technique_survives_round_trip(self) -> None:
        for path in OUTPUT_JSON_DIR.rglob("*.json"):
            raw = json.loads(path.read_text())
            session = TrainingSession.model_validate(raw)
            dumped = session.model_dump(mode="json")
            for ex_raw, ex_out in zip(raw["exercises"], dumped["exercises"]):
                for ws_raw, ws_out in zip(ex_raw.get("sets") or [], ex_out.get("sets") or []):
                    assert (ws_raw.get("failure_technique") is not None) == (
                        ws_out.get("failure_technique") is not None
                    ), f"failure_technique mismatch in {path.name}"
