"""Tests for parse_reps -- turning rep text as written into typed counts.

Every string here is either taken from a real input file or is the shape one of them takes.
The point of the design is that the model copies and Python converts, so these tests are the
whole safety net for the conversion half.
"""
from __future__ import annotations

import pytest

from traininglogs.agent.reps import parse_reps


class TestPlainCounts:
    @pytest.mark.parametrize("written,full", [("8", 8), ("12", 12), (" 10 ", 10), ("0", 0)])
    def test_a_bare_number(self, written: str, full: int) -> None:
        parsed = parse_reps(written)
        assert parsed.rep_count is not None
        assert (parsed.rep_count.full, parsed.rep_count.partial) == (full, 0)
        assert parsed.warning is None

    @pytest.mark.parametrize(
        "written,full",
        [
            ("12 catches", 12),          # adhoc_movement_skills_session.md
            ("20 taps - avg 290ms", 20), # adhoc_movement_skills_session.md
            ("5 attempts, 2 clean", 5),  # adhoc_calisthenics_rings_session.md
            ("8 reps - full lockout", 8),
        ],
    )
    def test_a_number_followed_by_description(self, written: str, full: int) -> None:
        """The description is already in the set's notes; only the count is needed here."""
        parsed = parse_reps(written)
        assert parsed.rep_count is not None
        assert parsed.rep_count.full == full
        assert parsed.warning is None


class TestPartials:
    @pytest.mark.parametrize("written,full,partial", [("8+1", 8, 1), ("10 + 2", 10, 2)])
    def test_full_plus_partial(self, written: str, full: int, partial: int) -> None:
        parsed = parse_reps(written)
        assert parsed.rep_count is not None
        assert (parsed.rep_count.full, parsed.rep_count.partial) == (full, partial)


class TestUnilateral:
    @pytest.mark.parametrize(
        "written",
        [
            "left 8, right 7",   # the form that actually appears in the corpus
            "left 8 right 7",
            "Left 8, Right 7",
            "L8/R7",             # short form -- plausible on a phone, absent from the corpus
            "l8/r7",
            "L 8 / R 7",
        ],
    )
    def test_explicit_per_side_counts(self, written: str) -> None:
        parsed = parse_reps(written)
        assert parsed.unilateral is not None
        assert parsed.unilateral.left.full == 8
        assert parsed.unilateral.right.full == 7
        assert parsed.rep_count is None

    def test_per_side_counts_with_partials(self) -> None:
        """"1. 25 x left 8 + 1, right 7" -- from inputs/, so this shape is real."""
        parsed = parse_reps("left 8 + 1, right 7")
        assert parsed.unilateral is not None
        assert (parsed.unilateral.left.full, parsed.unilateral.left.partial) == (8, 1)
        assert (parsed.unilateral.right.full, parsed.unilateral.right.partial) == (7, 0)

    def test_commentary_about_a_side_is_not_a_unilateral_count(self) -> None:
        """The Wrist Flexion defect, as a test.

        "12.5 x 13 - right did partial range only" means 13 reps on both arms, with a remark
        about the right one. The model now records reps as "13" and puts the remark in notes,
        so there is no field to mis-assign. This asserts the parser agrees.
        """
        parsed = parse_reps("13")
        assert parsed.rep_count is not None
        assert parsed.rep_count.full == 13
        assert parsed.unilateral is None


class TestNoCountWritten:
    @pytest.mark.parametrize(
        "written",
        [
            "feel", "Feel", "FEEL", "amrap", "max", "failure",
            "feel banded shoulder movement",   # appears 12x in the corpus
            "feel - very slow tempo to activate side delts",
        ],
    )
    def test_words_meaning_no_fixed_count(self, written: str) -> None:
        """"36 x feel" is a real warmup set with no rep count -- absent, not unparseable.
        A trailing description is common and must not turn it into a warning."""
        parsed = parse_reps(written)
        assert parsed.rep_count is None
        assert parsed.unilateral is None
        assert parsed.warning is None

    @pytest.mark.parametrize("written", [None, "", "   "])
    def test_nothing_written(self, written: str | None) -> None:
        parsed = parse_reps(written)
        assert parsed.rep_count is None
        assert parsed.warning is None


class TestUnparseable:
    @pytest.mark.parametrize("written", ["a few", "some reps", "??", "-"])
    def test_warns_rather_than_guessing(self, written: str) -> None:
        parsed = parse_reps(written)
        assert parsed.rep_count is None
        assert parsed.unilateral is None
        assert parsed.warning is not None
        assert written in parsed.warning

    def test_the_original_text_appears_in_the_warning(self) -> None:
        """Nothing is silently lost -- the warning names what could not be read, and the text as
        written stays on the extraction regardless."""
        assert "a few" in (parse_reps("a few").warning or "")
