"""card_edits: card-level edits -> extract edits, applied and re-validated. Pure, no LLM, no DB."""
from __future__ import annotations

from typing import Any

import pytest

from traininglogs.agent.card_edits import (
    EDITABLE_FIELDS,
    CardEdit,
    CardEditError,
    CardOp,
    apply_card_edits,
    apply_card_op,
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


def apply_card_op_on(extract: TrainingLogLLMExtract, op: str, path: str):
    return apply_card_op(extract, CardOp(op=op, path=path))


def _op(op: str, path: str, uncertain: list[str] | None = None):
    return apply_card_op_on(_extract(uncertain), op, path)


def _sets(extract: TrainingLogLLMExtract, ex: int = 0) -> list[tuple[int, float | None, int | None]]:
    return [
        (s.number, s.weight_kg, s.rep_count.full if s.rep_count else None)
        for s in extract.exercises[ex].sets
    ]


class TestAddSet:
    def test_append_copies_last_set_weight_and_reps_only(self) -> None:
        result, _, created = _op("add_set", "exercises.0")
        assert _sets(result) == [(1, 60.0, 12), (2, 60.0, 10), (3, 60.0, 10)]
        new = result.exercises[0].sets[2]
        assert new.rpe is None and new.notes is None and new.rep_quality_assessment is None
        assert created == "exercises.0.sets.2"

    def test_insert_after_a_set_renumbers_the_rest(self) -> None:
        """The real case: a missed set in the middle of an exercise."""
        result, _, created = _op("add_set", "exercises.0.sets.0")
        assert _sets(result) == [(1, 60.0, 12), (2, 60.0, 12), (3, 60.0, 10)]
        assert created == "exercises.0.sets.1"
        # The set that used to be second keeps its own RPE, now at position 2.
        assert result.exercises[0].sets[2].rpe == 9.0

    def test_insert_shifts_uncertain_paths(self) -> None:
        result, _, _ = _op(
            "add_set", "exercises.0.sets.0",
            uncertain=["exercises.0.sets.0.rpe", "exercises.0.sets.1.rpe", "date"],
        )
        assert result.uncertain_fields == ["exercises.0.sets.0.rpe", "exercises.0.sets.2.rpe", "date"]

    def test_into_an_exercise_with_no_sets(self) -> None:
        result, _, _ = _op("add_exercise", "")
        result, _, created = apply_card_op_on(result, "add_set", "exercises.1")
        assert created == "exercises.1.sets.0"
        assert result.exercises[1].sets[0].number == 1
        assert result.exercises[1].sets[0].weight_kg is None

    def test_records_one_list_level_edit(self) -> None:
        _, edits, _ = _op("add_set", "exercises.0")
        assert [e.path for e in edits] == ["exercises.0.sets"]
        assert [s["number"] for s in edits[0].value] == [1, 2, 3]

    @pytest.mark.parametrize("path", ["", "warmup.0", "exercises.0.warmup_sets.0"])
    def test_wrong_kind_of_line_rejected(self, path: str) -> None:
        with pytest.raises(CardEditError, match="can't be applied"):
            _op("add_set", path)

    @pytest.mark.parametrize("path", ["exercises.0.sets.9", "exercises.5"])
    def test_line_that_does_not_exist_rejected(self, path: str) -> None:
        with pytest.raises(CardEditError, match="out of range|no such line"):
            _op("add_set", path)


class TestAddWarmupSetAndExercise:
    def test_warmup_set_appended_copying_weight_and_reps(self) -> None:
        result, _, created = _op("add_warmup_set", "exercises.0")
        assert created == "exercises.0.warmup_sets.1"
        ws = result.exercises[0].warmup_sets[1]
        assert (ws.number, ws.weight_kg, ws.rep_count) == (2, 40.0, 10)

    def test_exercise_appended_with_placeholder_name(self) -> None:
        result, _, created = _op("add_exercise", "")
        assert created == "exercises.1"
        assert (result.exercises[1].number, result.exercises[1].name) == (2, "New exercise")

    def test_exercise_inserted_after_shifts_uncertain_paths(self) -> None:
        extract = _extract(["exercises.0.name"])
        two, _, _ = apply_card_op_on(extract, "add_exercise", "")
        two = two.model_copy(update={"uncertain_fields": ["exercises.1.sets.0.rpe"]})
        result, _, created = apply_card_op_on(two, "add_exercise", "exercises.0")
        assert created == "exercises.1"
        assert [e.number for e in result.exercises] == [1, 2, 3]
        assert result.uncertain_fields == ["exercises.2.sets.0.rpe"]


class TestRemove:
    def test_remove_set_renumbers_and_shifts_uncertain(self) -> None:
        result, edits, created = _op(
            "remove", "exercises.0.sets.0",
            uncertain=["exercises.0.sets.0.rpe", "exercises.0.sets.1.weight_kg", "focus"],
        )
        assert _sets(result) == [(1, 60.0, 10)]
        assert result.uncertain_fields == ["exercises.0.sets.0.weight_kg", "focus"]
        assert created is None
        assert [e.path for e in edits] == ["exercises.0.sets"]

    def test_remove_exercise(self) -> None:
        two, _, _ = _op("add_exercise", "")
        result, _, _ = apply_card_op_on(two, "remove", "exercises.0")
        assert [(e.number, e.name) for e in result.exercises] == [(1, "New exercise")]

    def test_remove_warmup_set_and_movement(self) -> None:
        result, _, _ = _op("remove", "exercises.0.warmup_sets.0")
        assert result.exercises[0].warmup_sets == []
        result, _, _ = _op("remove", "warmup.0")
        assert result.warmup == []

    def test_session_cannot_be_removed(self) -> None:
        with pytest.raises(CardEditError, match="can't be removed"):
            _op("remove", "")

    def test_out_of_range_rejected(self) -> None:
        with pytest.raises(CardEditError, match="out of range"):
            _op("remove", "exercises.0.sets.7")

    def test_original_extract_untouched(self) -> None:
        original = _extract()
        apply_card_op(original, CardOp(op="remove", path="exercises.0.sets.0"))
        assert len(original.exercises[0].sets) == 2
