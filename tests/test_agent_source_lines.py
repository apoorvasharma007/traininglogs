"""Tests for the two source-line checks in extraction.py.

Both checks answer a plain question about any extraction, in any input format:
  check_sources_are_real()       -- did the model read each set from a line that exists?
  check_sets_and_sources_match() -- does every set have a source, and every source a set?

Neither knows about weights, units, headers or exercise types on purpose, so the tests cover a
markdown block, a plain-prose block and a speech-style transcript to prove that.
"""
from __future__ import annotations

import pytest

from traininglogs.agent.extraction import (
    check_sets_and_sources_match,
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
            {"number": 1, "weight_kg": 90.0, "rep_count": {"full": 8, "partial": 0}},
            {"number": 2, "weight_kg": 90.0, "rep_count": {"full": 7, "partial": 0}, "rpe": 8.0},
        ],
        "warmup_sets": [{"number": 1, "weight_kg": 20.0, "rep_count": 8}],
        "set_sources": {"1": "1. 90kg x 8", "2": "2. 90kg x 7 RPE 8"},
        "warmup_sources": {"1": "1. 20kg x 8"},
    }
    base.update(overrides)
    return ExerciseExtract(**base)


class TestCheckSourcesAreReal:
    def test_clean_extraction_produces_no_warnings(self) -> None:
        assert check_sources_are_real(CHUNK, _extract()) == []

    def test_invented_source_line_is_flagged(self) -> None:
        extract = _extract(set_sources={"1": "1. 90kg x 8", "2": "2. 140kg x 12"})
        warnings = check_sources_are_real(CHUNK, extract)
        assert len(warnings) == 1
        assert "set 2" in warnings[0]
        assert "2. 140kg x 12" in warnings[0]

    def test_invented_warmup_source_is_flagged(self) -> None:
        extract = _extract(warmup_sources={"1": "1. 60kg x 3"})
        warnings = check_sources_are_real(CHUNK, extract)
        assert len(warnings) == 1
        assert "warmup 1" in warnings[0]

    def test_surrounding_whitespace_is_not_a_mismatch(self) -> None:
        extract = _extract(set_sources={"1": "  1. 90kg x 8  ", "2": "2. 90kg x 7 RPE 8"})
        assert check_sources_are_real(CHUNK, extract) == []

    def test_empty_source_is_not_flagged_as_invented(self) -> None:
        # An empty string means "not recorded", which is check_sets_and_sources_match's business.
        extract = _extract(set_sources={"1": "1. 90kg x 8", "2": ""})
        assert check_sources_are_real(CHUNK, extract) == []

    @pytest.mark.parametrize(
        "chunk,line",
        [
            ("Ring Support Hold\n1. 20s - straight arms, stable\n", "1. 20s - straight arms, stable"),
            ("did three sets of eight at ninety kilos last one was grindy", "at ninety kilos"),
            ("| 1 | 90 | 8 | RPE 7 |", "| 1 | 90 | 8 | RPE 7 |"),
        ],
    )
    def test_format_agnostic(self, chunk: str, line: str) -> None:
        """Works on calisthenics notation, a speech transcript, and a table row alike — the
        check is 'is this quote in the text', nothing more."""
        extract = _extract(
            sets=[{"number": 1, "duration_seconds": 20}],
            set_sources={"1": line},
            warmup_sets=None,
            warmup_sources={},
        )
        assert check_sources_are_real(chunk, extract) == []


class TestCheckSetsAndSourcesMatch:
    def test_clean_extraction_produces_no_warnings(self) -> None:
        assert check_sets_and_sources_match(_extract()) == []

    def test_set_without_a_source_is_flagged(self) -> None:
        extract = _extract(set_sources={"1": "1. 90kg x 8"})
        warnings = check_sets_and_sources_match(extract)
        assert len(warnings) == 1
        assert "set 2 has no source line recorded" in warnings[0]

    def test_source_without_a_set_is_flagged_as_possibly_dropped(self) -> None:
        """The shape that matters most: the model read a line, then didn't produce a set for it."""
        extract = _extract(
            sets=[{"number": 1, "weight_kg": 90.0, "rep_count": {"full": 8, "partial": 0}}]
        )
        warnings = check_sets_and_sources_match(extract)
        assert len(warnings) == 1
        assert "set 2" in warnings[0]
        assert "dropped" in warnings[0]

    def test_warmup_mismatch_is_flagged_independently_of_sets(self) -> None:
        extract = _extract(warmup_sources={})
        warnings = check_sets_and_sources_match(extract)
        assert len(warnings) == 1
        assert "warmup 1 has no source line recorded" in warnings[0]

    def test_no_sets_and_no_sources_is_clean(self) -> None:
        extract = _extract(sets=None, warmup_sets=None, set_sources={}, warmup_sources={})
        assert check_sets_and_sources_match(extract) == []
