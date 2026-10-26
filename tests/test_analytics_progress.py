"""analytics.progress: grouping sets into key lifts and other lifts by the exercise they count as.
Pure, no database."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from traininglogs.analytics.progress import lift_detail, lift_summaries

TODAY = date(2026, 10, 4)
SQUAT, BENCH, PULL_UP = "11111111-0000-4000-8000-000000000001", "11111111-0000-4000-8000-000000000002", "11111111-0000-4000-8000-000000000003"
LEG_EXTENSION, CABLE_FLY = "22222222-0000-4000-8000-000000000001", "22222222-0000-4000-8000-000000000002"


def r(session: str, day: date, exercise: str, weight, reps, rpe=None, number=1, goal=None,
      library: str | None = None, custom: str | None = None, bodyweight: bool = False) -> dict:
    return {"session_id": session, "date": day, "exercise": exercise, "number": number,
            "weight_kg": weight, "reps_full": reps, "left_reps_full": None,
            "right_reps_full": None, "rpe": rpe, "goal_weight_kg": goal,
            "library_exercise_id": library, "custom_exercise_id": custom, "bodyweight": bodyweight}


def lift(name: str, library: str | None = None, custom: str | None = None, bodyweight: bool = False) -> dict:
    return {"library_exercise_id": library, "custom_exercise_id": custom, "name": name, "bodyweight": bodyweight}


KEY_LIFTS = [
    lift("Squat (Barbell)", SQUAT), lift("Bench Press (Barbell)", BENCH),
    lift("Pull-up (Bodyweight)", PULL_UP, bodyweight=True),
]
ROWS = [
    # The second squat was logged as a custom exercise linked to Squat (Barbell): the read counts
    # it as the library exercise, under its name.
    r("a", date(2026, 9, 1), "Squat (Barbell)", Decimal("100"), 5, Decimal("8"), library=SQUAT),
    r("b", date(2026, 9, 8), "Squat (Barbell)", Decimal("105"), 5, Decimal("8"), goal=Decimal("110"), library=SQUAT),
    r("a", date(2026, 9, 1), "Pull-up (Bodyweight)", Decimal("0"), 8, library=PULL_UP, bodyweight=True),
    r("a", date(2026, 9, 1), "Leg Extension", 50, 10, custom=LEG_EXTENSION),
    r("b", date(2026, 9, 8), "Leg Extension", 52, 10, custom=LEG_EXTENSION),
    r("c", date(2026, 9, 15), "Leg Extension", 55, 10, custom=LEG_EXTENSION),
    r("a", date(2026, 9, 1), "Cable Fly", 20, 10, custom=CABLE_FLY),  # only 1 session: not shown
]


def test_key_lifts_listed_in_their_order() -> None:
    out = lift_summaries(ROWS, TODAY, KEY_LIFTS)
    assert [k["name"] for k in out["key_lifts"]] == ["Squat (Barbell)", "Bench Press (Barbell)", "Pull-up (Bodyweight)"]
    assert out["key_lifts"][0]["library_exercise_id"] == SQUAT


def test_key_lift_gathers_every_session_of_its_exercise() -> None:
    squat = lift_summaries(ROWS, TODAY, KEY_LIFTS)["key_lifts"][0]
    assert (squat["sessions"], squat["latest"], squat["last_date"]) == (2, 129.5, date(2026, 9, 8))


def test_key_lift_with_no_sessions() -> None:
    bench = lift_summaries(ROWS, TODAY, KEY_LIFTS)["key_lifts"][1]
    assert (bench["sessions"], bench["latest"], bench["best"], bench["trend"]) == (0, None, None, None)


def test_bodyweight_lift_uses_reps() -> None:
    pull = lift_summaries(ROWS, TODAY, KEY_LIFTS)["key_lifts"][2]
    assert (pull["metric"], pull["latest"]) == ("bodyweight_reps", 8.0)


def test_other_lifts_need_three_sessions() -> None:
    other = lift_summaries(ROWS, TODAY, KEY_LIFTS)["other_lifts"]
    assert [(o["name"], o["custom_exercise_id"], o["sessions"]) for o in other] == [("Leg Extension", LEG_EXTENSION, 3)]


def test_detail_for_a_key_lift() -> None:
    squat = lift_detail(ROWS, (SQUAT, None), TODAY, KEY_LIFTS)
    assert squat["name"] == "Squat (Barbell)"
    assert [p["value"] for p in squat["points"]] == [123.3, 129.5]
    assert squat["points"][1]["records"] == ["estimated_max", "heaviest"]
    assert squat["points"][1]["goal_weight_kg"] == 110.0


def test_detail_for_a_custom_exercise() -> None:
    assert lift_detail(ROWS, (None, LEG_EXTENSION), TODAY, KEY_LIFTS)["sessions"] == 3


def test_detail_for_a_key_lift_never_trained() -> None:
    assert lift_detail(ROWS, (BENCH, None), TODAY, KEY_LIFTS)["sessions"] == 0


def test_detail_unknown_lift() -> None:
    assert lift_detail(ROWS, ("33333333-0000-4000-8000-000000000001", None), TODAY, KEY_LIFTS) is None


def test_a_lift_not_pinned_moves_to_other_lifts() -> None:
    rows = ROWS + [r("c", date(2026, 9, 15), "Squat (Barbell)", Decimal("110"), 5, Decimal("8"), library=SQUAT)]
    other = lift_summaries(rows, TODAY, [lift("Leg Extension", custom=LEG_EXTENSION)])["other_lifts"]
    assert [(o["name"], o["sessions"]) for o in other] == [("Squat (Barbell)", 3)]
