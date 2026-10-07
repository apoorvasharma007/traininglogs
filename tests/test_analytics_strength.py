"""analytics.strength and analytics.key_lifts: estimated max, sessions, records, trend, key lifts.
Pure, no database."""
from __future__ import annotations

from datetime import date

import pytest

from traininglogs.analytics.key_lifts import KEY_LIFTS, key_lift_for, key_lift_named
from traininglogs.analytics.strength import (
    SetRow,
    bodyweight_points,
    estimate_max,
    mark_records,
    session_points,
    set_reps,
    trend,
)


def row(session: str, day: date, weight: float | None, reps: int | None, rpe: float | None = None,
        number: int = 1, goal: float | None = None, **kw) -> SetRow:
    return SetRow(session_id=session, date=day, exercise="Squat", number=number, weight_kg=weight,
                  reps_full=reps, rpe=rpe, goal_weight_kg=goal, **kw)


class TestEstimateMax:
    def test_rpe_adds_the_reps_left(self) -> None:
        # 5 reps at RPE 8: 2 reps left, so 7 effective reps.
        assert estimate_max(100, 5, 8) == (pytest.approx(123.3), "rpe")

    def test_one_at_rpe_9_equals_two_at_rpe_10(self) -> None:
        assert estimate_max(100, 1, 9)[0] == estimate_max(100, 2, 10)[0]

    def test_without_rpe_there_is_no_estimate(self) -> None:
        """Reps left are unknown; treating them as none would understate the max."""
        assert estimate_max(100, 5, None) is None

    def test_a_single_at_rpe_10_is_close_to_the_weight(self) -> None:
        assert estimate_max(140, 1, 10)[0] == pytest.approx(144.7)

    @pytest.mark.parametrize(("weight", "reps", "rpe"), [
        (0, 5, 8),        # bodyweight
        (None, 5, 8),
        (100, 0, 10),
        (100, 13, 9),     # too many reps to estimate from
        (100, None, 8),
        (100, 5, 5.5),    # too far from failure
    ])
    def test_sets_that_cant_support_an_estimate(self, weight, reps, rpe) -> None:
        assert estimate_max(weight, reps, rpe) is None


class TestSetReps:
    def test_bilateral(self) -> None:
        assert set_reps(row("s", date(2026, 9, 1), 30, 8)) == 8

    def test_unilateral_uses_the_weaker_side(self) -> None:
        assert set_reps(row("s", date(2026, 9, 1), 30, None, left_reps_full=8, right_reps_full=7)) == 7


class TestSessionPoints:
    def test_best_set_per_session_oldest_first(self) -> None:
        rows = [
            row("b", date(2026, 9, 3), 100, 5, 9, number=1),
            row("a", date(2026, 9, 1), 90, 5, 8, number=1),
            row("a", date(2026, 9, 1), 100, 3, 9, number=2, goal=105),
            row("a", date(2026, 9, 1), 40, 8, 4, number=3),  # RPE 4: not counted
        ]
        points = session_points(rows)
        assert [p.session_id for p in points] == ["a", "b"]
        first = points[0]
        assert (first.best_set.number, first.value, first.method) == (2, pytest.approx(113.3), "rpe")
        assert (first.heaviest_kg, first.goal_weight_kg, len(first.sets)) == (100, 105, 3)

    def test_session_with_nothing_countable_is_left_out(self) -> None:
        assert session_points([row("a", date(2026, 9, 1), 0, 10)]) == []

    def test_session_without_rpe_keeps_its_heaviest_set_and_no_estimate(self) -> None:
        rows = [
            row("a", date(2026, 9, 1), 100, 5, number=1),
            row("a", date(2026, 9, 1), 110, 3, number=2),
        ]
        [point] = session_points(rows)
        assert (point.value, point.method, point.heaviest_kg, point.best_set.number) == (None, None, 110, 2)

    def test_only_sets_with_rpe_make_the_estimate(self) -> None:
        rows = [
            row("a", date(2026, 9, 1), 140, 3, number=1),  # heavier, but no RPE
            row("a", date(2026, 9, 1), 100, 5, 8, number=2),
        ]
        [point] = session_points(rows)
        assert (point.best_set.number, point.value, point.heaviest_kg) == (2, pytest.approx(123.3), 140)


class TestRecords:
    def test_records_mark_sessions_that_beat_everything_before(self) -> None:
        points = session_points([
            row("a", date(2026, 9, 1), 100, 5, 8),
            row("b", date(2026, 9, 3), 105, 5, 8),   # new estimate and heaviest
            row("c", date(2026, 9, 5), 100, 3, 10),  # lower on both
            row("d", date(2026, 9, 7), 110, 1, 7),   # heavier, lower estimate
        ])
        mark_records(points)
        assert [p.records for p in points] == [[], ["estimated_max", "heaviest"], [], ["heaviest"]]


class TestBodyweight:
    def test_reps_at_bodyweight_and_added_weight_stay_separate(self) -> None:
        points = bodyweight_points([
            row("a", date(2026, 9, 1), 0, 6, 10),
            row("a", date(2026, 9, 1), 0, 8, 10, number=2),
            row("b", date(2026, 9, 3), 25, 3, 10),   # weighted only: no reps value
            row("c", date(2026, 9, 5), 0, 19, 10),
        ])
        assert [(p.value, p.heaviest_kg) for p in points] == [(8.0, None), (None, 25), (19.0, None)]
        mark_records(points, "reps")
        assert [p.records for p in points] == [[], [], ["reps"]]


class TestTrend:
    def points(self, *pairs):
        return [row(str(i), d, w, 5, 8) for i, (d, w) in enumerate(pairs)]

    def test_up_flat_down(self) -> None:
        today = date(2026, 10, 3)
        before, recent = date(2026, 8, 20), date(2026, 9, 25)
        assert trend(session_points(self.points((before, 100), (recent, 105))), today) == "up"
        assert trend(session_points(self.points((before, 100), (recent, 101))), today) == "flat"
        assert trend(session_points(self.points((before, 100), (recent, 95))), today) == "down"

    def test_not_enough_data(self) -> None:
        today = date(2026, 10, 3)
        assert trend(session_points(self.points((date(2026, 9, 25), 100))), today) is None


class TestKeyLifts:
    def test_variants_match_ignoring_case_and_spaces(self) -> None:
        assert key_lift_for("  Squats ").name == "Squat"
        assert key_lift_for("Bench press").name == "Bench Press"
        assert key_lift_for("Weighted Pull ups").name == "Pull-up"

    def test_no_fuzzy_merges(self) -> None:
        assert key_lift_for("Seated DB Shoulder Press") is None
        assert key_lift_for("Chinups") is None

    def test_lookup_by_display_name(self) -> None:
        assert key_lift_named("pull-up").measure == "bodyweight_reps"

    def test_no_name_claimed_twice(self) -> None:
        names = [n for lift in KEY_LIFTS for n in lift.names]
        assert len(names) == len(set(names))
