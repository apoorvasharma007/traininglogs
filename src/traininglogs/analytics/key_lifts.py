"""The lifts Progress shows first when the person hasn't pinned any: library exercises, by name,
since a library exercise's name is the same in every database and its id isn't."""
from __future__ import annotations

DEFAULT_KEY_LIFTS: tuple[str, ...] = (
    "Squat (Barbell)",
    "Bench Press (Barbell)",
    "Overhead Press (Barbell)",
    "Deadlift (Barbell)",
    "Clean (Barbell)",
    "Pull-up (Bodyweight)",
)
