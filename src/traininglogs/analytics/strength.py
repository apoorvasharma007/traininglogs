"""Estimated max per set and per session, personal records, and the recent trend.

Pure functions over set rows the caller loads (see `SetRow`); no database here.

Estimated max uses Epley's formula with the reps the lifter had left added on:

    estimated max = weight × (1 + (reps + RIR) / 30),   RIR = 10 − RPE

so 1 rep at RPE 9 and 2 reps at RPE 10 give the same answer, as they should. Published RPE charts
disagree with each other, so none is used. A set without an RPE gives no estimate: how many reps
were left is unknown, and guessing "none" understates the max.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

MAX_REPS = 12  # estimates from longer sets are unreliable
MIN_RPE = 6  # a set further than 4 reps from failure says too little about the max
TREND_WINDOW = timedelta(days=28)
FLAT_WITHIN = 0.02

Method = Literal["rpe"]
Trend = Literal["up", "flat", "down"]


@dataclass(frozen=True)
class SetRow:
    """One working set, as stored."""

    session_id: str
    date: date
    exercise: str
    number: int
    weight_kg: float | None
    reps_full: int | None
    left_reps_full: int | None = None
    right_reps_full: int | None = None
    rpe: float | None = None
    goal_weight_kg: float | None = None


def set_reps(row: SetRow) -> int | None:
    """Full reps; for a unilateral set, the weaker side, since that's the real limit."""
    if row.reps_full is not None:
        return row.reps_full
    sides = [r for r in (row.left_reps_full, row.right_reps_full) if r is not None]
    return min(sides) if sides else None


def estimate_max(weight_kg: float | None, reps: int | None, rpe: float | None) -> tuple[float, Method] | None:
    """(estimated max, method), or None for a set that can't support an estimate."""
    if weight_kg is None or weight_kg <= 0 or reps is None or not 1 <= reps <= MAX_REPS:
        return None
    if rpe is None or rpe < MIN_RPE:
        return None
    rir = 10 - rpe
    return round(weight_kg * (1 + (reps + rir) / 30), 1), "rpe"


@dataclass
class SessionPoint:
    """One session of one lift: its best estimate, the set behind it, and every counted set."""

    session_id: str
    date: date
    # Best estimated max, or for a bodyweight lift the best reps at bodyweight: None when that
    # session's sets were all weighted, which then show only through heaviest_kg.
    value: float | None
    method: Method | None
    best_set: SetRow
    heaviest_kg: float | None
    goal_weight_kg: float | None
    sets: list[SetRow] = field(default_factory=list)
    records: list[str] = field(default_factory=list)  # "estimated_max", "heaviest", "reps"


def session_points(rows: list[SetRow]) -> list[SessionPoint]:
    """Best estimated max per session, oldest first.

    A session with weighted sets but none that gives an estimate (no RPE) is kept with no value,
    its heaviest set as best_set, so it still shows through heaviest_kg. Sessions with no weighted
    set are left out."""
    by_session: dict[str, list[SetRow]] = {}
    for row in rows:
        by_session.setdefault(row.session_id, []).append(row)

    points = []
    for sets in by_session.values():
        estimates = [(estimate_max(s.weight_kg, set_reps(s), s.rpe), s) for s in sets]
        estimates = [(e, s) for e, s in estimates if e is not None]
        weighted = [s for s in sets if s.weight_kg and s.weight_kg > 0 and set_reps(s)]
        if estimates:
            (value, method), best = max(estimates, key=lambda pair: pair[0][0])
        elif weighted:
            value, method, best = None, None, max(weighted, key=lambda s: s.weight_kg)
        else:
            continue
        weights = [s.weight_kg for s in sets if s.weight_kg]
        points.append(SessionPoint(
            session_id=best.session_id, date=best.date, value=value, method=method, best_set=best,
            heaviest_kg=max(weights) if weights else None,
            goal_weight_kg=next((s.goal_weight_kg for s in sets if s.goal_weight_kg), None),
            sets=sorted(sets, key=lambda s: s.number),
        ))
    return sorted(points, key=lambda p: (p.date, p.session_id))


def bodyweight_points(rows: list[SetRow]) -> list[SessionPoint]:
    """Per session, oldest first: best reps at bodyweight, and the heaviest added weight.

    Two separate measures, never mixed: a session of only weighted sets has no reps value (it
    would otherwise read as a drop from 19 reps to 3), and shows through heaviest_kg alone."""
    by_session: dict[str, list[SetRow]] = {}
    for row in rows:
        by_session.setdefault(row.session_id, []).append(row)

    points = []
    for sets in by_session.values():
        at_bodyweight = [(set_reps(s), s) for s in sets if not s.weight_kg and set_reps(s)]
        weighted = [s for s in sets if s.weight_kg and set_reps(s)]
        if not at_bodyweight and not weighted:
            continue
        value: float | None
        if at_bodyweight:
            reps, best = max(at_bodyweight, key=lambda p: p[0])
            value = float(reps)
        else:
            best, value = max(weighted, key=lambda s: s.weight_kg), None
        points.append(SessionPoint(
            session_id=best.session_id, date=best.date, value=value, method=None,
            best_set=best, heaviest_kg=max((s.weight_kg for s in weighted), default=None),
            goal_weight_kg=None, sets=sorted(sets, key=lambda s: s.number),
        ))
    return sorted(points, key=lambda p: (p.date, p.session_id))


def mark_records(points: list[SessionPoint], value_record: str = "estimated_max") -> None:
    """Mark each session that beat every session before it, on its value and its heaviest weight.

    The first session sets the starting bar, so it isn't marked."""
    best_value = best_heaviest = None
    for p in points:
        if p.value is not None and best_value is not None and p.value > best_value:
            p.records.append(value_record)
        if p.heaviest_kg is not None and best_heaviest is not None and p.heaviest_kg > best_heaviest:
            p.records.append("heaviest")
        if p.value is not None:
            best_value = p.value if best_value is None else max(best_value, p.value)
        if p.heaviest_kg is not None:
            best_heaviest = p.heaviest_kg if best_heaviest is None else max(best_heaviest, p.heaviest_kg)


def trend(points: list[SessionPoint], today: date) -> Trend | None:
    """The best value in the last 4 weeks against the best in the 4 weeks before.

    None when either window has no session: not enough to say."""
    valued = [p for p in points if p.value is not None]
    recent = [p.value for p in valued if today - TREND_WINDOW < p.date <= today]
    before = [p.value for p in valued if today - 2 * TREND_WINDOW < p.date <= today - TREND_WINDOW]
    if not recent or not before:
        return None
    change = (max(recent) - max(before)) / max(before) if max(before) else 0
    if abs(change) <= FLAT_WITHIN:
        return "flat"
    return "up" if change > 0 else "down"
