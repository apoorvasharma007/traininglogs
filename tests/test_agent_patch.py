"""Applying edits to an extract.

The property this file exists to pin: fields the patch does not name cannot change. That used to
be a sentence in a prompt ("keep all unchanged fields exactly as they are") and is now a
consequence of copying the original and setting only the named paths.
"""
from __future__ import annotations

import pytest

from traininglogs.agent.patch import ExtractPatch, FieldEdit, PatchError, apply_edits

DATA = {
    "date": "2026-05-12",
    "focus": "Upper",
    "notes": None,
    "exercises": [
        {
            "number": 1,
            "name": "Bench Press",
            "sets": [
                {"number": 1, "weight_kg": 80.0, "rpe": 8.0},
                {"number": 2, "weight_kg": 80.0, "rpe": 9.0},
            ],
        },
        {"number": 2, "name": "Overhead Press", "sets": []},
    ],
}


def edit(path: str, value) -> FieldEdit:
    return FieldEdit(path=path, value=value)


class TestApplyingEdits:
    def test_sets_a_nested_value(self) -> None:
        out = apply_edits(DATA, [edit("exercises.0.sets.1.rpe", 10.0)])
        assert out["exercises"][0]["sets"][1]["rpe"] == 10.0

    def test_sets_a_top_level_value(self) -> None:
        assert apply_edits(DATA, [edit("focus", "Lower")])["focus"] == "Lower"

    def test_null_clears_a_field(self) -> None:
        assert apply_edits(DATA, [edit("focus", None)])["focus"] is None

    def test_replaces_a_whole_list(self) -> None:
        new_sets = [{"number": 1, "weight_kg": 40.0, "rpe": None}]
        out = apply_edits(DATA, [edit("exercises.1.sets", new_sets)])
        assert out["exercises"][1]["sets"] == new_sets

    def test_several_edits_all_land(self) -> None:
        out = apply_edits(DATA, [
            edit("focus", "Push"),
            edit("exercises.0.name", "Barbell Bench Press"),
            edit("exercises.0.sets.0.rpe", 7.5),
        ])
        assert out["focus"] == "Push"
        assert out["exercises"][0]["name"] == "Barbell Bench Press"
        assert out["exercises"][0]["sets"][0]["rpe"] == 7.5

    def test_negative_index_addresses_from_the_end(self) -> None:
        out = apply_edits(DATA, [edit("exercises.0.sets.-1.rpe", 10.0)])
        assert out["exercises"][0]["sets"][1]["rpe"] == 10.0

    def test_no_edits_is_a_faithful_copy(self) -> None:
        assert apply_edits(DATA, []) == DATA


class TestNothingElseChanges:
    def test_unnamed_fields_are_identical(self) -> None:
        out = apply_edits(DATA, [edit("exercises.0.sets.1.rpe", 10.0)])

        assert out["date"] == DATA["date"]
        assert out["focus"] == DATA["focus"]
        assert out["exercises"][0]["name"] == DATA["exercises"][0]["name"]
        assert out["exercises"][0]["sets"][0] == DATA["exercises"][0]["sets"][0]
        assert out["exercises"][1] == DATA["exercises"][1]

    def test_the_original_is_not_mutated(self) -> None:
        """The caller keeps the model's own reading. A patch that edited in place would
        destroy it — and with it the ability to say what the model said versus what the person
        changed."""
        before = DATA["exercises"][0]["sets"][1]["rpe"]
        apply_edits(DATA, [edit("exercises.0.sets.1.rpe", 10.0)])
        assert DATA["exercises"][0]["sets"][1]["rpe"] == before


class TestBadPathsFailLoudly:
    """A path that resolves to nothing must not be a silent no-op — the person would believe
    their correction landed."""

    def test_unknown_field(self) -> None:
        with pytest.raises(PatchError, match="is not a field here"):
            apply_edits(DATA, [edit("exercises.0.rpe", 9.0)])

    def test_unknown_nested_field(self) -> None:
        with pytest.raises(PatchError, match="is not a field here"):
            apply_edits(DATA, [edit("exercises.0.sets.0.tempo", "3-1-1")])

    def test_list_index_out_of_range(self) -> None:
        with pytest.raises(PatchError, match="out of range"):
            apply_edits(DATA, [edit("exercises.7.name", "Squat")])

    def test_appending_by_index_is_not_allowed(self) -> None:
        """Length changes go through replacing the whole list, so there is one way to do it."""
        with pytest.raises(PatchError, match="out of range"):
            apply_edits(DATA, [edit("exercises.0.sets.2", {"number": 3})])

    def test_word_where_a_position_belongs(self) -> None:
        with pytest.raises(PatchError, match="not a list position"):
            apply_edits(DATA, [edit("exercises.first.name", "Squat")])

    def test_indexing_into_a_scalar(self) -> None:
        with pytest.raises(PatchError):
            apply_edits(DATA, [edit("focus.0", "x")])

    def test_empty_path_is_rejected_at_the_model(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FieldEdit(path="   ", value=1)

    def test_one_bad_edit_does_not_half_apply_the_rest(self) -> None:
        """apply_edits works on a copy, so a failure leaves the caller's data untouched."""
        with pytest.raises(PatchError):
            apply_edits(DATA, [edit("focus", "Push"), edit("nope.0", 1)])
        assert DATA["focus"] == "Upper"


class TestThePatchSchemaIsSmall:
    def test_it_asks_for_edits_not_a_workout(self) -> None:
        schema = ExtractPatch.model_json_schema()
        assert set(schema["properties"]) == {"edits"}
        assert "exercises" not in schema["properties"]
