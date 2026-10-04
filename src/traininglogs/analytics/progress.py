"""The Progress view's data: key lifts first, then other lifts trained in 3 or more sessions.

Pure: takes the rows `db.fetch.get_working_set_rows` returns and builds what the API sends.
Key lifts gather every name variant listed in `key_lifts`; other lifts are grouped by name,
ignoring case, and shown under the spelling used most recently.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from traininglogs.analytics.key_lifts import KEY_LIFTS, KeyLift, key_lift_for, key_lift_named, normalise
from traininglogs.analytics.strength import (
    SessionPoint,
    SetRow,
    bodyweight_points,
    mark_records,
    session_points,
    trend,
)

MIN_SESSIONS_FOR_OTHER_LIFTS = 3


def _num(v: Any) -> Any:
    return float(v) if isinstance(v, Decimal) else v


def to_set_rows(rows: list[dict]) -> list[SetRow]:
    return [SetRow(**{k: _num(v) for k, v in r.items()}) for r in rows]


def _points(sets: list[SetRow], lift: KeyLift | None) -> list[SessionPoint]:
    if lift is not None and lift.measure == "bodyweight_reps":
        points = bodyweight_points(sets)
        mark_records(points, "reps")
    else:
        points = session_points(sets)
        mark_records(points, "estimated_max")
    return points


def _summary(name: str, lift: KeyLift | None, points: list[SessionPoint], today: date) -> dict:
    valued = [p.value for p in points if p.value is not None]
    return {
        "name": name,
        "measure": lift.measure if lift else "estimated_max",
        "sessions": len(points),
        "latest": valued[-1] if valued else None,
        "best": max(valued) if valued else None,
        "last_date": points[-1].date if points else None,
        "trend": trend(points, today),
    }


def _other_lift_groups(sets: list[SetRow]) -> dict[str, list[SetRow]]:
    groups: dict[str, list[SetRow]] = {}
    for s in sets:
        if key_lift_for(s.exercise) is None:
            groups.setdefault(normalise(s.exercise), []).append(s)
    return groups


def lift_summaries(rows: list[dict], today: date) -> dict:
    sets = to_set_rows(rows)
    key = []
    for lift in KEY_LIFTS:
        mine = [s for s in sets if key_lift_for(s.exercise) is lift]
        key.append(_summary(lift.name, lift, _points(mine, lift), today))

    other = []
    for group in _other_lift_groups(sets).values():
        points = _points(group, None)
        if len(points) >= MIN_SESSIONS_FOR_OTHER_LIFTS:
            other.append(_summary(group[-1].exercise.strip(), None, points, today))
    other.sort(key=lambda o: (-o["sessions"], o["name"].casefold()))
    return {"key_lifts": key, "other_lifts": other}


def lift_detail(rows: list[dict], name: str, today: date) -> dict | None:
    """One lift's sessions, oldest first, or None if no lift has that name."""
    sets = to_set_rows(rows)
    lift = key_lift_named(name)
    if lift is not None:
        mine = [s for s in sets if key_lift_for(s.exercise) is lift]
        display = lift.name
    else:
        mine = _other_lift_groups(sets).get(normalise(name), [])
        if not mine:
            return None
        display = mine[-1].exercise.strip()

    points = _points(mine, lift)
    return {
        **_summary(display, lift, points, today),
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
