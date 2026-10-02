"""Unit tests for the deterministic pre-chunking helpers: _locate_anchors and _chunk_exercises.
Pure functions, no LLM or provider involved — same testing convention as audit()'s isolated
tests.

Chunk boundaries are character offsets into the raw text, not line numbers — that's what lets
two exercises anchored on the same physical line (a short, casual capture with no line breaks
between them) both be located; a line-based search can only ever find the first of them.

Note: an earlier version of chunking used a positive CHUNK_TRAILING_OVERLAP_LINES "safety
margin," which was root-caused (via external research + direct verification against real
chunk output) to leak the next exercise's opening into the current chunk — producing a
failure pattern that looked like an LLM reliability problem ("lost in the middle") but was
actually a deterministic bug: a worker handed a 2-exercise chunk but told to extract the
*global* split position would miscount and misfire. Fixed by zeroing the overlap and having
assemble() pass position 1 (not the global position) whenever a chunk was successfully
isolated. See test_no_leak_of_next_exercises_content_into_current_chunk below."""
from __future__ import annotations

from traininglogs.agent.extraction import _chunk_exercises, _locate_anchors
from traininglogs.agent.schemas import ExercisePosition, ExerciseSplit


def _split(*entries: tuple[int, str, str]) -> ExerciseSplit:
    return ExerciseSplit(
        exercises=[
            ExercisePosition(position=p, name=n, anchor=a) for p, n, a in entries
        ]
    )


class TestLocateAnchors:
    def test_locates_each_anchor_in_order(self) -> None:
        text = "Bench Press\nSets:\n1. 80kg x 8\n\nOverhead Press\nSets:\n1. 40kg x 8\n"
        split = _split((1, "Bench Press", "Bench Press"), (2, "Overhead Press", "Overhead Press"))
        located = _locate_anchors(text, split)
        assert located == {1: text.index("Bench Press"), 2: text.index("Overhead Press")}

    def test_missing_anchor_is_omitted_not_fatal(self) -> None:
        text = "Bench Press\nSets:\n1. 80kg x 8\n"
        split = _split((1, "Bench Press", "Bench Press"), (2, "Squat", "Squat"))
        located = _locate_anchors(text, split)
        assert located == {1: 0}

    def test_sequential_search_disambiguates_repeated_anchor_text(self) -> None:
        """The exact bug found in live run 2: the same exercise name/line can legitimately
        appear more than once. A global find would map both occurrences to the first line;
        sequential search (starting after the previous match) must not."""
        text = "Lat Pulldown\nSets:\n1. 100kg x 8\n\nLat Pulldown\nSets:\n1. 90kg x 8\n"
        split = _split((1, "Lat Pulldown", "Lat Pulldown"), (2, "Lat Pulldown", "Lat Pulldown"))
        located = _locate_anchors(text, split)
        first = text.index("Lat Pulldown")
        second = text.index("Lat Pulldown", first + 1)
        assert located == {1: first, 2: second}
        assert located[1] != located[2]

    def test_partial_line_anchor_still_matches(self) -> None:
        text = "Bench Press (barbell, flat)\nSets:\n1. 80kg x 8\n"
        split = _split((1, "Bench Press", "Bench Press"))
        located = _locate_anchors(text, split)
        assert located == {1: 0}

    def test_two_exercises_on_the_same_line_are_both_located(self) -> None:
        """The bug this rewrite exists to fix: a short, casual capture with no line breaks
        between exercises. A line-based search can only ever find the first anchor, since it
        advances to the next *line* after a match — and there may be no next line at all."""
        text = "Push day. Bench press 60kg for 8. Incline db press 22kg for 10."
        split = _split((1, "Bench press", "Bench press"), (2, "Incline db press", "Incline db press"))
        located = _locate_anchors(text, split)
        assert located == {1: text.index("Bench press"), 2: text.index("Incline db press")}

    def test_matching_tolerates_curly_quotes_and_non_breaking_spaces(self) -> None:
        """A model asked to copy an anchor "verbatim" still silently retypes a curly apostrophe
        or a non-breaking space into its plain equivalent — the same drift _comparable() exists
        to tolerate elsewhere in this file (found for real on 2026-08-03). The anchor here is
        the plain-character version; the source text has the fancy one."""
        text = "Trainee’s Bench Press\nSets:\n1. 80kg x 8\n"
        split = _split((1, "Trainee's Bench Press", "Trainee's Bench Press"))
        located = _locate_anchors(text, split)
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

    def test_two_exercises_on_the_same_line_are_split_at_the_right_offset(self) -> None:
        text = "Push day. Bench press 60kg for 8. Incline db press 22kg for 10."
        split = _split((1, "Bench press", "Bench press"), (2, "Incline db press", "Incline db press"))
        chunks = _chunk_exercises(text, split)
        assert "Bench press 60kg for 8." in chunks[1]
        assert "Incline db press" not in chunks[1]
        assert "Incline db press 22kg for 10." in chunks[2]
        assert "Bench press" not in chunks[2]

    def test_out_of_order_position_labels_do_not_leak_across_chunks(self) -> None:
        """A chunk's own content is always tied to its own anchor -- position 2 in this test is
        the entry whose anchor is "Squat", so its chunk always starts there, whatever number
        the model called it. What's *not* guaranteed without care is the boundary between
        chunks: `_locate_anchors` returns offsets in the order the splitter's list was in, but
        if that list order doesn't match ascending position numbers (nothing enforces that it
        does), sorting boundaries by the declared number instead of by where anchors actually
        landed would pair one exercise's start with a different, wrongly-matched exercise's
        offset as its "end" -- slicing into a neighbor's content instead of stopping at it."""
        text = "Squat\nSets:\n1. 100kg x 5\n\nBench Press\nSets:\n1. 80kg x 8\n"
        # Listed in the order they appear in the text (Squat first), but the splitter called
        # the *later* text (Bench Press) position 1 and the earlier text (Squat) position 2.
        split = _split((2, "Squat", "Squat"), (1, "Bench Press", "Bench Press"))
        chunks = _chunk_exercises(text, split)
        assert set(chunks) == {1, 2}
        # Whichever label each chunk ended up filed under, its content is exactly one
        # exercise's isolated text -- never a slice spanning into the other's.
        for chunk in chunks.values():
            assert ("Squat" in chunk) != ("Bench Press" in chunk)
        assert "100kg" in chunks[2] and "80kg" not in chunks[2]
        assert "80kg" in chunks[1] and "100kg" not in chunks[1]
