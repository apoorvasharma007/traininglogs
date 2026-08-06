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


# The exercise-count check that used to be tested here was removed on 2026-08-06: assemble()
# appends exactly one exercise per split entry — the extracted one, or a placeholder when the
# worker fails — so the counts were equal by construction and the check could never fire. The
# guarantee it appeared to provide is covered where it actually lives, by
# test_agent_assembler.py::test_failed_worker_becomes_flagged_placeholder_not_a_crash.


class TestOrphanedRpeTokens:
    def test_rpe_present_in_text_and_extraction_produces_no_warning(self) -> None:
        split = ExerciseSplit(exercises=[ExercisePosition(position=1, name="Bench Press", anchor="Bench Press")])
        exercises = [_exercise(1, "Bench Press", sets=[_set(1, weight_kg=90.0, rpe=8.0)])]
        warnings = audit("Sets: 1. 90kg x 8\nRemarks: RPE: 8", exercises)
        assert warnings == []

    def test_rpe_in_text_missing_from_extraction_is_flagged(self) -> None:
        split = ExerciseSplit(exercises=[ExercisePosition(position=1, name="Bench Press", anchor="Bench Press")])
        exercises = [_exercise(1, "Bench Press", sets=[_set(1, weight_kg=90.0)])]
        warnings = audit("Sets: 1. 90kg x 8\nRemarks: RPE: 8", exercises)
        assert any("RPE 8.0" in w for w in warnings)

    def test_rpe_range_checks_the_upper_bound(self) -> None:
        # "RPE: 6-7" should be looked for as 7.0 (the convention's upper-bound rule), not 6.0.
        split = ExerciseSplit(exercises=[ExercisePosition(position=1, name="Bench Press", anchor="Bench Press")])
        exercises = [_exercise(1, "Bench Press", sets=[_set(1, weight_kg=90.0, rpe=7.0)])]
        warnings = audit("Remarks: RPE: 6-7", exercises)
        assert warnings == []

    def test_same_rpe_value_repeated_across_exercises_is_not_double_flagged(self) -> None:
        split = ExerciseSplit(exercises=[ExercisePosition(position=1, name="Bench Press", anchor="Bench Press")])
        exercises = [_exercise(1, "Bench Press", sets=[_set(1, weight_kg=90.0)])]
        warnings = audit("RPE: 8\nsome more text\nRPE: 8 again", exercises)
        rpe_warnings = [w for w in warnings if "RPE 8.0" in w]
        assert len(rpe_warnings) == 1

    def test_no_rpe_mentioned_produces_no_warning(self) -> None:
        split = ExerciseSplit(exercises=[ExercisePosition(position=1, name="Bench Press", anchor="Bench Press")])
        exercises = [_exercise(1, "Bench Press", sets=[_set(1, weight_kg=90.0)])]
        warnings = audit("Sets: 1. 90kg x 8, felt smooth", exercises)
        assert warnings == []
