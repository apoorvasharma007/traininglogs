"""Unit tests for the deterministic pre-chunking helpers added to solve the "lost in the
middle" position-drift/missing-sets problem found during live E2E testing (Step 8 of the
orchestration refactor): _locate_anchor_lines and _chunk_exercises. Pure functions, no LLM or
provider involved — same testing convention as audit()'s isolated tests."""
from __future__ import annotations

from traininglogs.agent.extraction import _chunk_exercises, _locate_anchor_lines
from traininglogs.agent.schemas import ExercisePosition, ExerciseSplit


def _split(*entries: tuple[int, str, str]) -> ExerciseSplit:
    return ExerciseSplit(
        exercises=[
            ExercisePosition(position=p, name=n, anchor=a) for p, n, a in entries
        ]
    )


class TestLocateAnchorLines:
    def test_locates_each_anchor_in_order(self) -> None:
        text = "Bench Press\nSets:\n1. 80kg x 8\n\nOverhead Press\nSets:\n1. 40kg x 8\n"
        lines = text.split("\n")
        split = _split((1, "Bench Press", "Bench Press"), (2, "Overhead Press", "Overhead Press"))
        located = _locate_anchor_lines(lines, split)
        assert located == {1: 0, 2: 4}

    def test_missing_anchor_is_omitted_not_fatal(self) -> None:
        text = "Bench Press\nSets:\n1. 80kg x 8\n"
        lines = text.split("\n")
        split = _split((1, "Bench Press", "Bench Press"), (2, "Squat", "Squat"))
        located = _locate_anchor_lines(lines, split)
        assert located == {1: 0}

    def test_sequential_search_disambiguates_repeated_anchor_text(self) -> None:
        """The exact bug found in live run 2: the same exercise name/line can legitimately
        appear more than once. A global find would map both occurrences to the first line;
        sequential search (starting after the previous match) must not."""
        text = "Lat Pulldown\nSets:\n1. 100kg x 8\n\nLat Pulldown\nSets:\n1. 90kg x 8\n"
        lines = text.split("\n")
        split = _split((1, "Lat Pulldown", "Lat Pulldown"), (2, "Lat Pulldown", "Lat Pulldown"))
        located = _locate_anchor_lines(lines, split)
        assert located == {1: 0, 2: 4}
        assert located[1] != located[2]

    def test_partial_line_anchor_still_matches(self) -> None:
        text = "Bench Press (barbell, flat)\nSets:\n1. 80kg x 8\n"
        lines = text.split("\n")
        split = _split((1, "Bench Press", "Bench Press"))
        located = _locate_anchor_lines(lines, split)
        assert located == {1: 0}


class TestChunkExercises:
    def test_two_exercises_split_at_the_right_boundary(self) -> None:
        text = "Bench Press\nSets:\n1. 80kg x 8\n\nOverhead Press\nSets:\n1. 40kg x 8\n"
        split = _split((1, "Bench Press", "Bench Press"), (2, "Overhead Press", "Overhead Press"))
        chunks = _chunk_exercises(text, split)
        assert "Bench Press" in chunks[1]
        assert "80kg" in chunks[1]
        assert "Overhead Press" in chunks[2]
        assert "40kg" in chunks[2]

    def test_first_chunk_does_not_run_to_end_of_document(self) -> None:
        text = (
            "Bench Press\nSets:\n1. 80kg x 8\n\n"
            "Overhead Press\nWarmup:\n1. 20kg x 8\nSets:\n1. 40kg x 8\nRemarks:\nfelt good\n"
        )
        split = _split((1, "Bench Press", "Bench Press"), (2, "Overhead Press", "Overhead Press"))
        chunks = _chunk_exercises(text, split)
        # A little trailing overlap into exercise 2 is expected and fine, but chunk 1 must not
        # reach as far as exercise 2's own Sets: weight — that would defeat the point of chunking.
        assert "40kg" not in chunks[1]

    def test_last_chunk_runs_to_end_of_document(self) -> None:
        text = "Bench Press\nSets:\n1. 80kg x 8\nRemarks:\nfelt good\n"
        split = _split((1, "Bench Press", "Bench Press"))
        chunks = _chunk_exercises(text, split)
        assert "felt good" in chunks[1]

    def test_trailing_overlap_included_but_bounded(self) -> None:
        """A little overlap past the next exercise's anchor is fine (a trailing remark might
        run a line or two past the boundary) — but the chunk must not run all the way through
        a long stretch of unrelated content after it, or chunking wouldn't narrow anything.
        Deliberately doesn't pin the exact overlap size — that's a tunable implementation
        detail, not a behavior callers should depend on."""
        source_lines = (
            ["Bench Press", "Sets:", "1. 80kg x 8", "Overhead Press"]
            + [f"unrelated tail line {i}" for i in range(20)]
        )
        text = "\n".join(source_lines)
        split = _split((1, "Bench Press", "Bench Press"), (2, "Overhead Press", "Overhead Press"))
        chunks = _chunk_exercises(text, split)

        assert "Overhead Press" in chunks[1]
        assert "unrelated tail line 15" not in chunks[1]

    def test_missing_anchor_omits_that_position_from_chunks(self) -> None:
        text = "Bench Press\nSets:\n1. 80kg x 8\n"
        split = _split((1, "Bench Press", "Bench Press"), (2, "Squat", "Squat"))
        chunks = _chunk_exercises(text, split)
        assert 1 in chunks
        assert 2 not in chunks

    def test_no_index_error_when_overlap_would_exceed_document_length(self) -> None:
        text = "Bench Press\nSets:\n1. 80kg x 8\n\nSquat\nSets:\n1. 100kg x 5\n"
        split = _split((1, "Bench Press", "Bench Press"), (2, "Squat", "Squat"))
        chunks = _chunk_exercises(text, split)
        assert "100kg" in chunks[2]
