"""The lifts the Progress view shows first, and which logged names count as each.

Chosen by Apoorva. Matching is exact, ignoring case and surrounding spaces: a fuzzy match would
merge lifts that aren't the same ("Shoulder Press", the barbell press, must not pick up "Seated DB
Shoulder Press"). Stored names are never changed; this only decides what counts when reading.
To add a variant someone types, add it here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Measure = Literal["estimated_max", "bodyweight_reps"]


@dataclass(frozen=True)
class KeyLift:
    name: str
    names: tuple[str, ...]  # every logged name that counts as this lift, lowercase
    # "bodyweight_reps" for lifts done mostly at bodyweight: the app stores no bodyweight, so an
    # estimated max would be meaningless and best reps is shown instead.
    measure: Measure = "estimated_max"


KEY_LIFTS: tuple[KeyLift, ...] = (
    KeyLift("Squat", ("squat", "squats")),
    KeyLift("Bench Press", ("bench press",)),
    KeyLift("Shoulder Press", ("shoulder press",)),
    KeyLift("Deadlift", ("deadlift",)),
    KeyLift("Barbell Clean", ("barbell clean",)),
    KeyLift("Pull-up", ("pull ups", "weighted pull up", "weighted pull ups"), "bodyweight_reps"),
)


def normalise(name: str) -> str:
    """The form names are compared in: lowercase, outer spaces removed."""
    return name.strip().casefold()


def key_lift_for(exercise_name: str) -> KeyLift | None:
    n = normalise(exercise_name)
    return next((lift for lift in KEY_LIFTS if n in lift.names), None)


def key_lift_named(name: str) -> KeyLift | None:
    n = normalise(name)
    return next((lift for lift in KEY_LIFTS if normalise(lift.name) == n), None)
