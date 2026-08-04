"""Unit tests for audit() — the deterministic, LLM-free drop-check added in Step 6 of the
orchestration refactor. Exercised in isolation (not through assemble()) with hand-built
Exercise objects, per the plan's ask for explicit false-positive/false-negative coverage."""
from __future__ import annotations

from traininglogs.agent.extraction import audit
from traininglogs.agent.schemas import ExercisePosition, ExerciseSplit
from traininglogs.models.models import Exercise, RepCount, WarmupSet, WorkingSet


def _exercise(number: int, name: str, sets: list[WorkingSet] | None = None, **kwargs) -> Exercise:
    return Exercise(number=number, name=name, sets=sets, **kwargs)


def _set(number: int, weight_kg: float | None = None, rpe: float | None = None) -> WorkingSet:
    return WorkingSet(
        number=number,
        weight_kg=weight_kg,
        rpe=rpe,
        rep_count=RepCount(full=8, partial=0) if weight_kg is not None else None,
    )


class TestExerciseCountMismatch:
    def test_matching_counts_produce_no_warning(self) -> None:
        split = ExerciseSplit(exercises=[ExercisePosition(position=1, name="Bench Press", anchor="Bench Press")])
        exercises = [_exercise(1, "Bench Press")]
        assert audit("some text", split, exercises) == []

    def test_fewer_exercises_than_split_produces_warning(self) -> None:
        split = ExerciseSplit(
            exercises=[
                ExercisePosition(position=1, name="Bench Press", anchor="Bench Press"),
                ExercisePosition(position=2, name="Overhead Press", anchor="Overhead Press"),
            ]
        )
        exercises = [_exercise(1, "Bench Press")]
        warnings = audit("text", split, exercises)
        assert any("count mismatch" in w for w in warnings)
        assert any("2 exercises" in w and "1 were assembled" in w for w in warnings)


class TestOrphanedRpeTokens:
    def test_rpe_present_in_text_and_extraction_produces_no_warning(self) -> None:
        split = ExerciseSplit(exercises=[ExercisePosition(position=1, name="Bench Press", anchor="Bench Press")])
        exercises = [_exercise(1, "Bench Press", sets=[_set(1, weight_kg=90.0, rpe=8.0)])]
        warnings = audit("Sets: 1. 90kg x 8\nRemarks: RPE: 8", split, exercises)
        assert warnings == []

    def test_rpe_in_text_missing_from_extraction_is_flagged(self) -> None:
        split = ExerciseSplit(exercises=[ExercisePosition(position=1, name="Bench Press", anchor="Bench Press")])
        exercises = [_exercise(1, "Bench Press", sets=[_set(1, weight_kg=90.0)])]
        warnings = audit("Sets: 1. 90kg x 8\nRemarks: RPE: 8", split, exercises)
        assert any("RPE 8.0" in w for w in warnings)

    def test_rpe_range_checks_the_upper_bound(self) -> None:
        # "RPE: 6-7" should be looked for as 7.0 (the convention's upper-bound rule), not 6.0.
        split = ExerciseSplit(exercises=[ExercisePosition(position=1, name="Bench Press", anchor="Bench Press")])
        exercises = [_exercise(1, "Bench Press", sets=[_set(1, weight_kg=90.0, rpe=7.0)])]
        warnings = audit("Remarks: RPE: 6-7", split, exercises)
        assert warnings == []

    def test_same_rpe_value_repeated_across_exercises_is_not_double_flagged(self) -> None:
        split = ExerciseSplit(exercises=[ExercisePosition(position=1, name="Bench Press", anchor="Bench Press")])
        exercises = [_exercise(1, "Bench Press", sets=[_set(1, weight_kg=90.0)])]
        warnings = audit("RPE: 8\nsome more text\nRPE: 8 again", split, exercises)
        rpe_warnings = [w for w in warnings if "RPE 8.0" in w]
        assert len(rpe_warnings) == 1

    def test_no_rpe_mentioned_produces_no_warning(self) -> None:
        split = ExerciseSplit(exercises=[ExercisePosition(position=1, name="Bench Press", anchor="Bench Press")])
        exercises = [_exercise(1, "Bench Press", sets=[_set(1, weight_kg=90.0)])]
        warnings = audit("Sets: 1. 90kg x 8, felt smooth", split, exercises)
        assert warnings == []
