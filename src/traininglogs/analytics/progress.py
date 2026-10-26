"""The Progress view's data: key lifts first, then other lifts trained in 3 or more sessions.

Pure: takes the rows `db.fetch.get_working_set_rows` returns and the key lifts
`db.fetch.get_key_lifts` returns, and builds what the API sends. A lift is the exercise a set counts
as: a library exercise (a custom exercise linked to one counts as it) or a custom exercise.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from traininglogs.analytics.strength import (
    SessionPoint,
    SetRow,
    bodyweight_points,
    mark_records,
    session_points,
    trend,
)

MIN_SESSIONS_FOR_OTHER_LIFTS = 3

# (library_exercise_id, custom_exercise_id), exactly one set: which exercise a lift is.
LiftRef = tuple[str | None, str | None]


def _num(v: Any) -> Any:
    return float(v) if isinstance(v, Decimal) else v


def to_set_rows(rows: list[dict]) -> list[SetRow]:
    return [SetRow(**{k: _num(v) for k, v in r.items()}) for r in rows]


def _by_lift(sets: list[SetRow]) -> dict[LiftRef, list[SetRow]]:
    groups: dict[LiftRef, list[SetRow]] = {}
    for s in sets:
        groups.setdefault((s.library_exercise_id, s.custom_exercise_id), []).append(s)
    return groups


def _lift(s: SetRow) -> dict:
    return {
        "library_exercise_id": s.library_exercise_id, "custom_exercise_id": s.custom_exercise_id,
        "name": s.exercise, "bodyweight": s.bodyweight,
    }


def _ref(lift: dict) -> LiftRef:
    return (lift["library_exercise_id"], lift["custom_exercise_id"])


def _points(sets: list[SetRow], bodyweight: bool) -> list[SessionPoint]:
    if bodyweight:
        points = bodyweight_points(sets)
        mark_records(points, "reps")
    else:
        points = session_points(sets)
        mark_records(points, "estimated_max")
    return points


def _summary(lift: dict, points: list[SessionPoint], today: date) -> dict:
    valued = [p.value for p in points if p.value is not None]
    return {
        "library_exercise_id": lift["library_exercise_id"],
        "custom_exercise_id": lift["custom_exercise_id"],
        "name": lift["name"],
        "metric": "bodyweight_reps" if lift["bodyweight"] else "estimated_max",
        "sessions": len(points),
        "latest": valued[-1] if valued else None,
        "best": max(valued) if valued else None,
        "last_date": points[-1].date if points else None,
        "trend": trend(points, today),
    }


def lift_summaries(rows: list[dict], today: date, key_lifts: list[dict]) -> dict:
    groups = _by_lift(to_set_rows(rows))
    key = [_summary(k, _points(groups.get(_ref(k), []), k["bodyweight"]), today) for k in key_lifts]
    pinned = {_ref(k) for k in key_lifts}
    other = []
    for ref, group in groups.items():
        lift = _lift(group[-1])
        points = _points(group, lift["bodyweight"])
        if ref not in pinned and len(points) >= MIN_SESSIONS_FOR_OTHER_LIFTS:
            other.append(_summary(lift, points, today))
    other.sort(key=lambda o: (-o["sessions"], o["name"].casefold()))
    return {"key_lifts": key, "other_lifts": other}


def lift_detail(rows: list[dict], ref: LiftRef, today: date, key_lifts: list[dict]) -> dict | None:
    """One lift's sessions, oldest first, or None when it's neither trained nor a key lift."""
    mine = _by_lift(to_set_rows(rows)).get(ref, [])
    lift = _lift(mine[-1]) if mine else next((k for k in key_lifts if _ref(k) == ref), None)
    if lift is None:
        return None
    points = _points(mine, lift["bodyweight"])
    return {
        **_summary(lift, points, today),
        "points": [
            {
                "session_id": p.session_id,
                "date": p.date,
                "value": p.value,
                "method": p.method,
                "heaviest_kg": p.heaviest_kg,
                "goal_weight_kg": p.goal_weight_kg,
                "records": p.records,
                "best_set": {"number": p.best_set.number, "weight_kg": p.best_set.weight_kg,
                             "reps": p.best_set.reps_full, "rpe": p.best_set.rpe},
                "sets": [{"number": s.number, "weight_kg": s.weight_kg, "reps_full": s.reps_full,
                          "left_reps_full": s.left_reps_full, "right_reps_full": s.right_reps_full,
                          "rpe": s.rpe} for s in p.sets],
            }
            for p in points
        ],
    }
