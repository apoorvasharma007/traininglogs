"""analytics.progress: grouping sets into key lifts and other lifts. Pure, no database."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from traininglogs.analytics.progress import lift_detail, lift_summaries

TODAY = date(2026, 10, 4)


def r(session: str, day: date, exercise: str, weight, reps, rpe=None, number=1, goal=None) -> dict:
    return {"session_id": session, "date": day, "exercise": exercise, "number": number,
            "weight_kg": weight, "reps_full": reps, "left_reps_full": None,
            "right_reps_full": None, "rpe": rpe, "goal_weight_kg": goal}


ROWS = [
    r("a", date(2026, 9, 1), "Squats", Decimal("100"), 5, Decimal("8")),
    r("b", date(2026, 9, 8), "Squat", Decimal("105"), 5, Decimal("8"), goal=Decimal("110")),
    r("a", date(2026, 9, 1), "Pull ups", Decimal("0"), 8),
    r("a", date(2026, 9, 1), "Leg Extension", 50, 10),
    r("b", date(2026, 9, 8), "leg extension", 52, 10),
    r("c", date(2026, 9, 15), "Leg extension ", 55, 10),
    r("a", date(2026, 9, 1), "Cable Fly", 20, 10),  # only 1 session: not shown
]


def test_key_lifts_always_listed_in_order() -> None:
    out = lift_summaries(ROWS, TODAY)
    assert [k["name"] for k in out["key_lifts"]] == [
        "Squat", "Bench Press", "Shoulder Press", "Deadlift", "Barbell Clean", "Pull-up"
    ]


def test_key_lift_gathers_its_variants() -> None:
    squat = lift_summaries(ROWS, TODAY)["key_lifts"][0]
    assert (squat["sessions"], squat["latest"], squat["last_date"]) == (2, 129.5, date(2026, 9, 8))


def test_key_lift_with_no_sessions() -> None:
    bench = lift_summaries(ROWS, TODAY)["key_lifts"][1]
    assert (bench["sessions"], bench["latest"], bench["best"], bench["trend"]) == (0, None, None, None)


def test_bodyweight_key_lift_uses_reps() -> None:
    pull = lift_summaries(ROWS, TODAY)["key_lifts"][5]
    assert (pull["measure"], pull["latest"]) == ("bodyweight_reps", 8.0)


def test_other_lifts_need_three_sessions_and_group_ignoring_case() -> None:
    other = lift_summaries(ROWS, TODAY)["other_lifts"]
    assert [(o["name"], o["sessions"]) for o in other] == [("Leg extension", 3)]


def test_detail_for_a_key_lift_by_display_name() -> None:
    squat = lift_detail(ROWS, "squat", TODAY)
    assert squat["name"] == "Squat"
    assert [p["value"] for p in squat["points"]] == [123.3, 129.5]
    assert squat["points"][1]["records"] == ["estimated_max", "heaviest"]
    assert squat["points"][1]["goal_weight_kg"] == 110.0


def test_detail_for_an_other_lift_by_any_casing() -> None:
    assert lift_detail(ROWS, "LEG EXTENSION", TODAY)["sessions"] == 3


def test_detail_unknown_lift() -> None:
    assert lift_detail(ROWS, "Nordic curl", TODAY) is None


def test_chosen_key_lifts_replace_the_built_in_list_in_their_order() -> None:
    out = lift_summaries(ROWS, TODAY, ["Leg Extension", "squat"])
    assert [k["name"] for k in out["key_lifts"]] == ["Leg Extension", "Squat"]
    # A built-in lift chosen by any spelling keeps all its name variants.
    assert out["key_lifts"][1]["sessions"] == 2
    assert out["key_lifts"][0]["sessions"] == 3


def test_a_built_in_lift_not_chosen_moves_to_other_lifts_with_its_variants() -> None:
    rows = ROWS + [r("c", date(2026, 9, 15), "squats", Decimal("110"), 5, Decimal("8"))]
    other = lift_summaries(rows, TODAY, ["Leg extension"])["other_lifts"]
    assert [(o["name"], o["sessions"]) for o in other] == [("Squat", 3)]
