"""analytics.corrections: counting the corrections log. Pure, no DB."""
from __future__ import annotations

import pytest

from traininglogs.analytics.corrections import path_pattern, summarize


@pytest.mark.parametrize(
    ("path", "pattern"),
    [
        ("exercises.3.sets.1.rpe", "exercises.*.sets.*.rpe"),
        ("exercises.12.name", "exercises.*.name"),
        ("date", "date"),
        ("session_duration_minutes", "session_duration_minutes"),
        ("exercises.0.sets", "exercises.*.sets"),
        ("warmup.2", "warmup.*"),
        ("exercises.0.sets.0.rep_count.full", "exercises.*.sets.*.rep_count.full"),
    ],
)
def test_path_pattern(path: str, pattern: str) -> None:
    assert path_pattern(path) == pattern


def _manual(*paths: str) -> dict:
    return {"source": "manual", "edits": [{"path": p, "value": 1} for p in paths]}


def test_counts_by_pattern_and_source_most_corrected_first() -> None:
    summary = summarize({
        "x1": [
            _manual("exercises.0.sets.0.rpe", "exercises.1.sets.2.rpe"),
            {"source": "ai", "instruction": "fix date", "edits": [{"path": "date", "value": "d"}]},
        ],
        "x2": [_manual("exercises.0.sets.1.rpe", "exercises.0.name")],
    })
    assert [(f.pattern, dict(f.by_source), len(f.sessions)) for f in summary.fields] == [
        ("exercises.*.sets.*.rpe", {"manual": 3}, 2),
        ("date", {"ai": 1}, 1),
        ("exercises.*.name", {"manual": 1}, 1),
    ]


def test_records_without_source_count_as_ai() -> None:
    summary = summarize({"x1": [{"instruction": "old", "edits": [{"path": "focus", "value": "a"}]}]})
    assert dict(summary.fields[0].by_source) == {"ai": 1}


def test_ops_counted_by_type_not_as_field_edits() -> None:
    op = {"source": "manual", "op": "add_set", "path": "exercises.0",
          "edits": [{"path": "exercises.0.sets", "value": []}]}
    summary = summarize({"x1": [op, op, {**op, "op": "remove"}]})
    assert summary.ops == {"add_set": 2, "remove": 1}
    assert summary.fields == []


def test_session_counts() -> None:
    summary = summarize({"x1": [_manual("date")], "x2": [], "x3": None})
    assert (summary.sessions_with_corrections, summary.sessions_total) == (1, 3)


def test_a_reps_edit_counts_once_as_reps() -> None:
    """A reps edit writes rep_count and unilateral_rep_count together; that's one change."""
    record = _manual("exercises.0.sets.1.rep_count", "exercises.0.sets.1.unilateral_rep_count")
    summary = summarize({"x1": [record]})
    assert [(f.pattern, f.total) for f in summary.fields] == [("exercises.*.sets.*.reps", 1)]


def test_warmup_rep_count_is_its_own_field() -> None:
    summary = summarize({"x1": [_manual("exercises.0.warmup_sets.0.rep_count")]})
    assert [f.pattern for f in summary.fields] == ["exercises.*.warmup_sets.*.rep_count"]
