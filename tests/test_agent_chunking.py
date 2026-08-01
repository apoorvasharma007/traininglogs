"""Unit tests for the deterministic pre-chunking helpers added during Step 8 of the
orchestration refactor: _locate_anchor_lines and _chunk_exercises. Pure functions, no LLM or
provider involved — same testing convention as audit()'s isolated tests.

Note: an earlier version of chunking used a positive CHUNK_TRAILING_OVERLAP_LINES "safety
margin," which was root-caused (via external research + direct verification against real
chunk output) to leak the next exercise's opening into the current chunk — producing a
failure pattern that looked like an LLM reliability problem ("lost in the middle") but was
actually a deterministic bug: a worker handed a 2-exercise chunk but told to extract the
*global* split position would miscount and misfire. Fixed by zeroing the overlap and having
assemble() pass position 1 (not the global position) whenever a chunk was successfully
isolated. See test_no_leak_of_next_exercises_content_into_current_chunk below."""
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

    def test_no_leak_of_next_exercises_content_into_current_chunk(self) -> None:
        """Regression test for a real production bug: a chunk that leaks even a little of the
        next exercise's opening (its name + first warmup line) makes that chunk look like it
        contains two exercises. A worker handed such a chunk and told "extract exercise number
        N" (the global split position) would count blocks in the leaked fragment and either
        pick the wrong one, refuse (out of range), or return empty/garbage — exactly the
        failure pattern that was misdiagnosed as an LLM reliability issue before this was
        root-caused. A chunk must contain ONLY its own exercise's content, nothing more."""
        text = (
            "Bench Press\nSets:\n1. 80kg x 8\n\n"
            "Overhead Press\nWarmup:\n1. 20kg x 8\nSets:\n1. 40kg x 8\nRemarks:\nfelt good\n"
        )
        split = _split((1, "Bench Press", "Bench Press"), (2, "Overhead Press", "Overhead Press"))
        chunks = _chunk_exercises(text, split)
        assert "Overhead Press" not in chunks[1]
        assert "40kg" not in chunks[1]
        assert "20kg" not in chunks[1]

    def test_last_chunk_runs_to_end_of_document(self) -> None:
        text = "Bench Press\nSets:\n1. 80kg x 8\nRemarks:\nfelt good\n"
        split = _split((1, "Bench Press", "Bench Press"))
        chunks = _chunk_exercises(text, split)
        assert "felt good" in chunks[1]

    def test_current_exercises_own_trailing_remarks_are_not_cut_off(self) -> None:
        """The current exercise's own content (including trailing remarks) always sits before
        the next exercise's anchor line, so a chunk needs no overlap margin to keep it intact —
        zero overlap is correct, not merely tolerated."""
        text = (
            "Bench Press\nSets:\n1. 80kg x 8\nRemarks:\nfelt heavy but clean\n\n"
            "Overhead Press\nSets:\n1. 40kg x 8\n"
        )
        split = _split((1, "Bench Press", "Bench Press"), (2, "Overhead Press", "Overhead Press"))
        chunks = _chunk_exercises(text, split)
        assert "felt heavy but clean" in chunks[1]
        assert "Overhead Press" not in chunks[1]

    def test_missing_anchor_omits_that_position_from_chunks(self) -> None:
        text = "Bench Press\nSets:\n1. 80kg x 8\n"
        split = _split((1, "Bench Press", "Bench Press"), (2, "Squat", "Squat"))
        chunks = _chunk_exercises(text, split)
        assert 1 in chunks
        assert 2 not in chunks
