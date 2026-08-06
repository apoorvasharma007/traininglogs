"""Tests for the two source-line checks in extraction.py.

Both answer a plain question about any extraction, in any input format:
  check_sources_are_real()              -- did the model read each set from a line that exists?
  check_sets_are_numbered_and_sourced() -- does every set carry a source, and do the numbers run 1..n?

Neither knows about weights, units, headers or exercise types on purpose, so the tests cover a
markdown block, a plain-prose transcript and a table row to prove that.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from traininglogs.agent.extraction import (
    check_sets_are_numbered_and_sourced,
    check_sources_are_real,
)
from traininglogs.agent.schemas import ExerciseExtract

CHUNK = """Bench Press
Warmup:
1. 20kg x 8
Sets:
1. 90kg x 8
2. 90kg x 7 RPE 8
"""


def _extract(**overrides) -> ExerciseExtract:
    base = {
        "number": 1,
        "name": "Bench Press",
        "sets": [
            {"number": 1, "source_line": "1. 90kg x 8", "weight_kg": 90.0, "reps": "8"},
            {"number": 2, "source_line": "2. 90kg x 7 RPE 8", "weight_kg": 90.0,
             "reps": "7", "rpe": 8.0},
        ],
        "warmup_sets": [
            {"number": 1, "source_line": "1. 20kg x 8", "weight_kg": 20.0, "reps": "8"}
        ],
    }
    base.update(overrides)
    return ExerciseExtract(**base)


class TestCheckSourcesAreReal:
    def test_clean_extraction_produces_no_warnings(self) -> None:
        assert check_sources_are_real(CHUNK, _extract()) == []

    def test_invented_source_line_is_flagged(self) -> None:
        extract = _extract(sets=[
            {"number": 1, "source_line": "1. 90kg x 8", "reps": "8"},
            {"number": 2, "source_line": "2. 140kg x 12", "reps": "12"},
        ])
        warnings = check_sources_are_real(CHUNK, extract)
        assert len(warnings) == 1
        assert "set 2" in warnings[0]
        assert "2. 140kg x 12" in warnings[0]

    def test_invented_warmup_source_is_flagged(self) -> None:
        extract = _extract(warmup_sets=[
            {"number": 1, "source_line": "1. 60kg x 3", "weight_kg": 60.0, "reps": "3"}
        ])
        warnings = check_sources_are_real(CHUNK, extract)
        assert len(warnings) == 1
        assert "warmup 1" in warnings[0]

    def test_surrounding_whitespace_is_not_a_mismatch(self) -> None:
        extract = _extract(sets=[
            {"number": 1, "source_line": "  1. 90kg x 8  ", "reps": "8"},
            {"number": 2, "source_line": "2. 90kg x 7 RPE 8", "reps": "7"},
        ])
        assert check_sources_are_real(CHUNK, extract) == []

    @pytest.mark.parametrize(
        "chunk,line",
        [
            ("Ring Support Hold\n1. 20s - straight arms, stable\n",
             "1. 20s - straight arms, stable"),
            ("did three sets of eight at ninety kilos last one was grindy", "at ninety kilos"),
            ("| 1 | 90 | 8 | RPE 7 |", "| 1 | 90 | 8 | RPE 7 |"),
        ],
    )
    def test_format_agnostic(self, chunk: str, line: str) -> None:
        """Calisthenics notation, a speech transcript and a table row alike — the check is
        'is this quote in the text', and nothing more."""
        extract = _extract(
            sets=[{"number": 1, "source_line": line, "duration_seconds": 20}],
            warmup_sets=None,
        )
        assert check_sources_are_real(chunk, extract) == []


class TestSourceComparisonIgnoresTranscriptionDifferences:
    """Both were real false alarms on 2026-08-03: the model read the right line and typed a
    plain character where the file had a typographic one."""

    def test_curly_apostrophe_typed_back_as_a_straight_one(self) -> None:
        chunk = "1. 63 x 10 good - since it’s already tired\n"
        extract = _extract(
            sets=[{"number": 1, "source_line": "1. 63 x 10 good - since it's already tired"}],
            warmup_sets=None,
        )
        assert check_sources_are_real(chunk, extract) == []

    def test_non_breaking_space_typed_back_as_an_ordinary_one(self) -> None:
        chunk = "2. 0 x 4  learning\n"
        extract = _extract(
            sets=[{"number": 1, "source_line": "2. 0 x 4 learning"}], warmup_sets=None
        )
        assert check_sources_are_real(chunk, extract) == []

    def test_a_genuinely_different_line_is_still_flagged(self) -> None:
        """The normalising must not loosen into uselessness."""
        chunk = "1. 63 x 10 RPE 10 good\n"
        extract = _extract(
            sets=[{"number": 1, "source_line": "1. 57 x 12 RPE 9 good"}], warmup_sets=None
        )
        assert len(check_sources_are_real(chunk, extract)) == 1


class TestCheckSetsAreNumberedAndSourced:
    def test_clean_extraction_produces_no_warnings(self) -> None:
        assert check_sets_are_numbered_and_sourced(_extract()) == []

    def test_empty_source_line_is_flagged(self) -> None:
        extract = _extract(sets=[
            {"number": 1, "source_line": "1. 90kg x 8", "reps": "8"},
            {"number": 2, "source_line": "   ", "reps": "7"},
        ])
        warnings = check_sets_are_numbered_and_sourced(extract)
        assert any("set 2 has no source line recorded" in w for w in warnings)

    def test_a_gap_in_set_numbers_is_flagged(self) -> None:
        """The shape a dropped set leaves behind."""
        extract = _extract(sets=[
            {"number": 1, "source_line": "1. 90kg x 8", "reps": "8"},
            {"number": 3, "source_line": "3. 90kg x 6", "reps": "6"},
        ])
        warnings = check_sets_are_numbered_and_sourced(extract)
        assert any("[1, 3]" in w and "[1, 2]" in w for w in warnings)

    def test_duplicate_set_numbers_are_flagged(self) -> None:
        extract = _extract(sets=[
            {"number": 1, "source_line": "1. 90kg x 8", "reps": "8"},
            {"number": 1, "source_line": "2. 90kg x 7", "reps": "7"},
        ])
        assert check_sets_are_numbered_and_sourced(extract) != []

    def test_warmup_numbering_is_checked_independently_of_sets(self) -> None:
        extract = _extract(warmup_sets=[
            {"number": 2, "source_line": "1. 20kg x 8", "weight_kg": 20.0, "reps": "8"}
        ])
        warnings = check_sets_are_numbered_and_sourced(extract)
        assert any("warmup numbers" in w for w in warnings)

    def test_an_exercise_with_no_sets_cannot_be_built_at_all(self) -> None:
        """These checks iterate over the sets that came back, so zero sets means zero findings —
        which is exactly how a worker returning nothing used to pass as clean data. The gap is
        closed one level up now: an extract with no sets is rejected on construction, so it can
        never reach these checks."""
        with pytest.raises(ValidationError, match="no working sets and no warmup sets"):
            _extract(sets=None, warmup_sets=None)


class TestProjectionToExercise:
    def test_rep_text_becomes_typed_counts(self) -> None:
        exercise, warnings = _extract().to_exercise(1)
        assert warnings == []
        assert exercise.sets[0].rep_count.full == 8
        assert exercise.sets[1].rep_count.full == 7
        assert exercise.warmup_sets[0].rep_count == 8   # plain int on WarmupSet

    def test_unreadable_rep_text_warns_rather_than_guessing(self) -> None:
        extract = _extract(sets=[
            {"number": 1, "source_line": "1. 90kg x a few", "weight_kg": 90.0, "reps": "a few"}
        ])
        exercise, warnings = extract.to_exercise(1)
        assert exercise.sets[0].rep_count is None
        assert any("a few" in w for w in warnings)

    def test_classification_fields_are_left_unset_not_invented(self) -> None:
        exercise, _ = _extract().to_exercise(1)
        for field in ("tags", "modality", "movement_pattern", "form_cues"):
            assert getattr(exercise, field) is None

    def test_source_lines_do_not_reach_the_production_model(self) -> None:
        exercise, _ = _extract().to_exercise(1)
        assert not hasattr(exercise.sets[0], "source_line")
