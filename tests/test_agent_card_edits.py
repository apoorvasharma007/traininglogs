"""card_edits: card-level edits -> extract edits, applied and re-validated. Pure, no LLM, no DB."""
from __future__ import annotations

from typing import Any

import pytest

from traininglogs.agent.card_edits import (
    EDITABLE_FIELDS,
    CardEdit,
    CardEditError,
    apply_card_edits,
    element_kind,
    to_field_edits,
)
from traininglogs.agent.schemas import TrainingLogLLMExtract


def _extract(uncertain: list[str] | None = None) -> TrainingLogLLMExtract:
    return TrainingLogLLMExtract.model_validate({
        "date": "2026-10-01",
        "focus": "Push",
        "session_duration_minutes": 60,
        "warmup": [{"number": 1, "name": "Arm circles", "reps": 20}],
        "exercises": [
            {
                "number": 1,
                "name": "Bench",
                "warmup_sets": [{"number": 1, "weight_kg": 40.0, "rep_count": 10}],
                "sets": [
                    {"number": 1, "weight_kg": 60.0, "rep_count": {"full": 12, "partial": 0},
                     "rpe": 8.0},
                    {"number": 2, "weight_kg": 60.0, "rep_count": {"full": 10, "partial": 0},
                     "rpe": 9.0},
                ],
            }
        ],
        "uncertain_fields": uncertain or [],
    })


def _apply(*edits: dict[str, Any], uncertain: list[str] | None = None) -> TrainingLogLLMExtract:
    result, _ = apply_card_edits(_extract(uncertain), [CardEdit(**e) for e in edits])
    return result


class TestElementKind:
    @pytest.mark.parametrize(
        ("path", "kind"),
        [
            ("", "session"),
            ("exercises.0", "exercise"),
            ("exercises.2.sets.1", "set"),
            ("exercises.0.warmup_sets.3", "warmup_set"),
            ("warmup.0", "movement"),
            ("cooldown.4", "movement"),
        ],
    )
    def test_kinds(self, path: str, kind: str) -> None:
        assert element_kind(path) == kind

    @pytest.mark.parametrize(
        "path", ["exercises", "exercises.x", "exercises.0.sets", "foo.0", "exercises.0.sets.0.rpe"]
    )
    def test_unknown_shapes_rejected(self, path: str) -> None:
        with pytest.raises(CardEditError, match="not a card element"):
            element_kind(path)


class TestMapping:
    def test_card_name_maps_to_extract_name(self) -> None:
        edits = to_field_edits(CardEdit(path="", field="duration_minutes", value=75))
        assert [(e.path, e.value) for e in edits] == [("session_duration_minutes", 75)]

    def test_quality_maps_to_rep_quality_assessment(self) -> None:
        edits = to_field_edits(CardEdit(path="exercises.0.sets.1", field="quality", value="good"))
        assert [e.path for e in edits] == ["exercises.0.sets.1.rep_quality_assessment"]

    def test_field_not_in_allowlist_rejected(self) -> None:
        with pytest.raises(CardEditError, match="can't be edited"):
            to_field_edits(CardEdit(path="exercises.0.sets.0", field="failure_technique", value="x"))

    def test_field_from_another_kind_rejected(self) -> None:
        # `name` is editable on an exercise, not on a set.
        with pytest.raises(CardEditError, match="can't be edited"):
            to_field_edits(CardEdit(path="exercises.0.sets.0", field="name", value="x"))

    def test_every_allowlisted_extract_field_exists_on_its_model(self) -> None:
        """Guards the table against typos: each mapped extract field is a real field."""
        from traininglogs.models.models import Exercise, SessionWarmup, WarmupSet, WorkingSet

        models = {
            "session": TrainingLogLLMExtract,
            "exercise": Exercise,
            "set": WorkingSet,
            "warmup_set": WarmupSet,
            "movement": SessionWarmup,
        }
        for kind, fields in EDITABLE_FIELDS.items():
            for extract_field in fields.values():
                assert extract_field in models[kind].model_fields, (kind, extract_field)


class TestApply:
    def test_number_edit(self) -> None:
        result = _apply({"path": "exercises.0.sets.1", "field": "weight_kg", "value": 62.5})
        assert result.exercises[0].sets[1].weight_kg == 62.5
        assert result.exercises[0].sets[0].weight_kg == 60.0

    def test_string_from_input_box_is_coerced(self) -> None:
        result = _apply({"path": "exercises.0.sets.0", "field": "rpe", "value": "8.5"})
        assert result.exercises[0].sets[0].rpe == 8.5

    def test_empty_string_clears(self) -> None:
        result = _apply({"path": "exercises.0.sets.0", "field": "rpe", "value": ""})
        assert result.exercises[0].sets[0].rpe is None

    def test_session_level_edit(self) -> None:
        assert _apply({"path": "", "field": "focus", "value": "Upper"}).focus == "Upper"

    def test_movement_and_warmup_set_edits(self) -> None:
        result = _apply(
            {"path": "warmup.0", "field": "reps", "value": 30},
            {"path": "exercises.0.warmup_sets.0", "field": "rep_count", "value": 8},
        )
        assert result.warmup[0].reps == 30
        assert result.exercises[0].warmup_sets[0].rep_count == 8

    def test_validator_rejection_names_the_field(self) -> None:
        with pytest.raises(CardEditError, match=r"exercises\.0\.sets\.0\.rpe"):
            _apply({"path": "exercises.0.sets.0", "field": "rpe", "value": 85})

    def test_out_of_range_position_rejected(self) -> None:
        with pytest.raises(CardEditError, match="out of range"):
            _apply({"path": "exercises.0.sets.5", "field": "rpe", "value": 8})

    def test_original_extract_untouched(self) -> None:
        original = _extract()
        apply_card_edits(original, [CardEdit(path="", field="focus", value="Upper")])
        assert original.focus == "Push"

    def test_returns_the_extract_edits_for_the_corrections_log(self) -> None:
        _, edits = apply_card_edits(
            _extract(), [CardEdit(path="", field="duration_minutes", value=75)]
        )
        assert [e.model_dump() for e in edits] == [
            {"path": "session_duration_minutes", "value": 75}
        ]


class TestReps:
    def test_plain(self) -> None:
        s = _apply({"path": "exercises.0.sets.0", "field": "reps", "value": "15"}).exercises[0].sets[0]
        assert (s.rep_count.full, s.rep_count.partial) == (15, 0)
        assert s.unilateral_rep_count is None

    def test_partial(self) -> None:
        s = _apply({"path": "exercises.0.sets.0", "field": "reps", "value": "8+2"}).exercises[0].sets[0]
        assert (s.rep_count.full, s.rep_count.partial) == (8, 2)

    def test_unilateral_replaces_bilateral(self) -> None:
        s = _apply({"path": "exercises.0.sets.0", "field": "reps", "value": "L8/R7"}).exercises[0].sets[0]
        assert s.rep_count is None
        assert (s.unilateral_rep_count.left.full, s.unilateral_rep_count.right.full) == (8, 7)

    def test_unreadable_reps_rejected_not_wiped(self) -> None:
        with pytest.raises(CardEditError, match="couldn't read reps"):
            _apply({"path": "exercises.0.sets.0", "field": "reps", "value": "feel"})

    def test_empty_clears_both(self) -> None:
        s = _apply({"path": "exercises.0.sets.0", "field": "reps", "value": ""}).exercises[0].sets[0]
        assert s.rep_count is None and s.unilateral_rep_count is None


class TestUncertainFields:
    def test_edited_field_no_longer_uncertain(self) -> None:
        result = _apply(
            {"path": "exercises.0.sets.1", "field": "rpe", "value": 9.5},
            uncertain=["exercises.0.sets.1.rpe", "exercises.0.sets.1.weight_kg", "date"],
        )
        assert result.uncertain_fields == ["exercises.0.sets.1.weight_kg", "date"]

    def test_card_name_and_nested_paths_cleared_for_reps(self) -> None:
        result = _apply(
            {"path": "exercises.0.sets.0", "field": "reps", "value": "12"},
            uncertain=["exercises.0.sets.0.reps", "exercises.0.sets.0.rep_count.full"],
        )
        assert result.uncertain_fields == []

    def test_renamed_session_field_cleared(self) -> None:
        result = _apply(
            {"path": "", "field": "duration_minutes", "value": 70},
            uncertain=["session_duration_minutes"],
        )
        assert result.uncertain_fields == []
