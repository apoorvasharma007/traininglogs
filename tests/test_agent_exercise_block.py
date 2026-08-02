"""Unit tests for parse_exercise_block, the deterministic per-exercise block parser added in
the extraction-accuracy fix (see extraction-accuracy-plan.md). Pure function, no LLM or
provider involved — same testing convention as _chunk_exercises's tests.

Written before src/traininglogs/agent/exercise_block.py exists, per CLAUDE.md test-first phase
order — this file is expected to fail on import until that module is written.

Block texts below are copied verbatim from
tests/fixtures/valid/programmed_push_pull_session_with_remarks.md so this test doesn't depend
on _chunk_exercises (a different module) to slice them correctly.
"""
from __future__ import annotations

from traininglogs.agent.exercise_block import parse_exercise_block

BENCH_PRESS = """Bench Press
Warmup:
1. 20kg x 8
2. 40kg x 6
3. 60kg x 4
4. 80kg x 3
Sets:
1. 90kg x 8
2. 90kg x 8
3. 90kg x 8
4. 90kg x 8

Remarks:
1. RPE: 6-7
2. 75% of 1RM.
3. All set in single breath.
4. Utilising almost none leg drive.
"""

INCLINE_DB_PRESS = """Incline DB Press
Warmup:
1. 40kg x 4
2. 60kg x 4
Sets:
1. 80kg x 8
2. 80kg x 9
3. 80kg x 6

Remarks:
1. RPE: 6-7.
2. Left shoulder felt off, mostly because of kettlebell windmills.
"""

CHEST_SUPPORTED_ROWS = """Chest Supported Rows
Warmup:
1. 40kg x 5
Sets:
1. 60kg x 8
2. 60kg x 8
3. 60kg x 8

Remarks:
1. Range didn’t feel good.
"""

LAT_PULLDOWN = """Lat Pulldown
Warmup:
1. 45kg x 5
Sets:
1. 100kg x 8
2. 100kg x 8
3. 100kg x 8

Remarks:
1. RPE: 8
"""

LATERAL_RAISE = """Lateral Raise
Warmup:
Sets:
1. 10kg x 15
2. 10kg x 15
3. 10kg x 15

Remarks:
1. RPE: 8
"""

TRICEPS_PUSHDOWN = """Triceps Pushdown
Warmup:
1. 20.4kg x 5
Sets:
1. 36.3kg x 10
2. 36.3kg x 10
3. 36.3kg x 9

Remarks:
1. RPE: 8
"""

# Realistic irregular formats (plan's own examples) that DeepTrainingParser's line parsers
# can't parse — the all-or-nothing gate must fall back to None, not a partial result.
TUCK_PLANCHE_HOLD = """Tuck Planche Hold
Warmup:
Sets:
1. 18s - tuck, clean
2. 15s - tuck, clean
3. 12s - tuck, clean, band-assisted

Remarks:
building toward straddle
"""

BAND_ASSISTED_PULLUPS = """Band-Assisted Pull-ups
Warmup:
Sets:
1. 5 attempts, 2 clean - band-assisted
2. 5 attempts, 3 clean - band-assisted

Remarks:
progressing
"""


class TestRegularBlocksAllParse:
    def test_bench_press(self) -> None:
        parsed = parse_exercise_block(BENCH_PRESS)
        assert parsed is not None
        assert [w["weight_kg"] for w in parsed.warmup_sets] == [20.0, 40.0, 60.0, 80.0]
        assert [s["weight_kg"] for s in parsed.sets] == [90.0, 90.0, 90.0, 90.0]
        assert [s["number"] for s in parsed.sets] == [1, 2, 3, 4]
        assert parsed.exercise_rpe == 7.0  # "RPE: 6-7" -> upper bound

    def test_incline_db_press(self) -> None:
        parsed = parse_exercise_block(INCLINE_DB_PRESS)
        assert parsed is not None
        assert [w["weight_kg"] for w in parsed.warmup_sets] == [40.0, 60.0]
        assert [s["weight_kg"] for s in parsed.sets] == [80.0, 80.0, 80.0]
        assert [s["rep_count"]["full"] for s in parsed.sets] == [8, 9, 6]
        assert parsed.exercise_rpe == 7.0  # "RPE: 6-7. " -> trailing punctuation doesn't matter

    def test_chest_supported_rows_has_no_exercise_rpe(self) -> None:
        """This exercise's remarks never mention RPE at all in the real fixture — a genuine
        absence, not a parsing failure. exercise_rpe must be None, not 0 or a crash."""
        parsed = parse_exercise_block(CHEST_SUPPORTED_ROWS)
        assert parsed is not None
        assert [w["weight_kg"] for w in parsed.warmup_sets] == [40.0]
        assert [s["weight_kg"] for s in parsed.sets] == [60.0, 60.0, 60.0]
        assert parsed.exercise_rpe is None

    def test_lat_pulldown(self) -> None:
        parsed = parse_exercise_block(LAT_PULLDOWN)
        assert parsed is not None
        assert [s["weight_kg"] for s in parsed.sets] == [100.0, 100.0, 100.0]
        assert parsed.exercise_rpe == 8.0  # single-value "RPE: 8", not a range

    def test_lateral_raise_empty_warmup_section(self) -> None:
        """The one exercise in the fixture with a 'Warmup:' header immediately followed by
        'Sets:' — zero warmup lines, not a parse failure."""
        parsed = parse_exercise_block(LATERAL_RAISE)
        assert parsed is not None
        assert parsed.warmup_sets == []
        assert [s["weight_kg"] for s in parsed.sets] == [10.0, 10.0, 10.0]
        assert [s["rep_count"]["full"] for s in parsed.sets] == [15, 15, 15]
        assert parsed.exercise_rpe == 8.0

    def test_triceps_pushdown_decimal_weights(self) -> None:
        parsed = parse_exercise_block(TRICEPS_PUSHDOWN)
        assert parsed is not None
        assert parsed.warmup_sets[0]["weight_kg"] == 20.4
        assert [s["weight_kg"] for s in parsed.sets] == [36.3, 36.3, 36.3]
        assert parsed.exercise_rpe == 8.0


class TestIrregularBlocksFallBackToNone:
    def test_timed_hold_notation_returns_none(self) -> None:
        assert parse_exercise_block(TUCK_PLANCHE_HOLD) is None

    def test_attempts_notation_returns_none(self) -> None:
        assert parse_exercise_block(BAND_ASSISTED_PULLUPS) is None
