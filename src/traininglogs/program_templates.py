"""Ready-made programs to copy from. Kept in code while there are a few starter ones; a larger
collection would move to the database, behind the same /templates calls. Each exercise is a library
exercise, written by its name: a library exercise's name is the same in every database, its id
isn't."""
from __future__ import annotations

from typing import Any

from psycopg2.extensions import connection as Connection

from traininglogs.api.schemas import ProgramTemplate


def _ex(name: str, sets: int, reps: int | None, warmup: int = 0, alternatives: tuple[str, ...] = ()) -> dict[str, Any]:
    """reps None means as many as you can."""
    return dict(
        name=name, warmup_sets=warmup, working_sets=sets, target_reps=reps, amrap=reps is None,
        alternatives=list(alternatives),
    )


def _workout(name: str, *exercises: dict[str, Any]) -> dict[str, Any]:
    return dict(name=name, exercises=list(exercises))


_PUSH = _workout(
    "Push",
    _ex("Bench Press (Barbell)", 4, 6, warmup=2),
    _ex("Overhead Press (Barbell)", 3, 8, warmup=2),
    _ex("Incline Press (Dumbbell, 45 Degree)", 3, 10),
    _ex("Lateral Raise (Dumbbell)", 3, 12),
    _ex("Triceps Pressdown (Cable, Rope)", 3, 12),
)
_PULL = _workout(
    "Pull",
    _ex("Deadlift (Barbell)", 3, 5, warmup=2),
    _ex("Pull-up (Bodyweight)", 3, None, alternatives=("Lat Pulldown (Cable, Wide Grip)",)),
    _ex("Row (Barbell)", 3, 8, warmup=2),
    _ex("Face Pull (Cable)", 3, 15),
    _ex("Biceps Curl (Dumbbell)", 3, 12),
)
_LEGS = _workout(
    "Legs",
    _ex("Squat (Barbell)", 4, 6, warmup=2),
    _ex("Romanian Deadlift (Barbell)", 3, 8, warmup=2),
    _ex("Leg Press (Machine)", 3, 10),
    _ex("Leg Curl (Machine, Seated)", 3, 12),
    _ex("Calf Raise (Machine, Standing)", 3, 15),
)
_UPPER_A = _workout(
    "Upper A",
    _ex("Bench Press (Barbell)", 4, 6, warmup=2),
    _ex("Row (Barbell)", 4, 6, warmup=2),
    _ex("Overhead Press (Barbell)", 3, 8, warmup=2),
    _ex("Lat Pulldown (Cable, Wide Grip)", 3, 10),
    _ex("Biceps Curl (Dumbbell)", 3, 12),
)
_LOWER_A = _workout(
    "Lower A",
    _ex("Squat (Barbell)", 4, 6, warmup=2),
    _ex("Romanian Deadlift (Barbell)", 3, 8, warmup=2),
    _ex("Leg Press (Machine)", 3, 10),
    _ex("Calf Raise (Machine, Standing)", 3, 15),
)

_TEMPLATES: list[dict[str, Any]] = [
    dict(
        id="5x5-strength", name="5×5 strength", days="3 days a week",
        workouts=[
            _workout("A", _ex("Squat (Barbell)", 5, 5, warmup=2), _ex("Bench Press (Barbell)", 5, 5, warmup=2), _ex("Row (Barbell)", 5, 5, warmup=2)),
            _workout("B", _ex("Squat (Barbell)", 5, 5, warmup=2), _ex("Overhead Press (Barbell)", 5, 5, warmup=2), _ex("Deadlift (Barbell)", 1, 5, warmup=2)),
        ],
    ),
    dict(id="push-pull-legs", name="Push / pull / legs", days="3 or 6 days a week", workouts=[_PUSH, _PULL, _LEGS]),
    dict(
        id="upper-lower", name="Upper / lower", days="4 days a week",
        workouts=[
            _UPPER_A,
            _LOWER_A,
            _workout(
                "Upper B",
                _ex("Overhead Press (Barbell)", 4, 6, warmup=2),
                _ex("Pull-up (Bodyweight)", 4, None, alternatives=("Lat Pulldown (Cable, Wide Grip)",)),
                _ex("Incline Press (Dumbbell, 45 Degree)", 3, 10),
                _ex("Row (Cable, Seated, Neutral Grip)", 3, 10),
                _ex("Triceps Pressdown (Cable, Rope)", 3, 12),
            ),
            _workout(
                "Lower B",
                _ex("Deadlift (Barbell)", 3, 5, warmup=2),
                _ex("Front Squat (Barbell)", 3, 8, warmup=2),
                _ex("Walking Lunge (Dumbbell)", 3, 10),
                _ex("Leg Curl (Machine, Seated)", 3, 12),
            ),
        ],
    ),
    dict(
        id="upper-lower-ppl", name="Upper / lower / PPL", days="5 days a week",
        workouts=[{**_UPPER_A, "name": "Upper"}, {**_LOWER_A, "name": "Lower"}, _PUSH, _PULL, _LEGS],
    ),
]


def template_names() -> set[str]:
    """Every library exercise the templates use."""
    return {
        name
        for t in _TEMPLATES for w in t["workouts"] for e in w["exercises"]
        for name in (e["name"], *e["alternatives"])
    }


def templates(conn: Connection) -> list[ProgramTemplate]:
    """The templates, each exercise with this database's library id."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT name, id::text FROM library_exercises WHERE name = ANY(%s)", (sorted(template_names()),)
        )
        ids = dict(cur.fetchall())

    def exercise(e: dict[str, Any]) -> dict[str, Any]:
        alternatives = [{"library_exercise_id": ids[a], "name": a} for a in e["alternatives"]]
        return {**e, "library_exercise_id": ids[e["name"]], "alternatives": alternatives}

    return [
        ProgramTemplate.model_validate(
            {**t, "workouts": [{**w, "exercises": [exercise(e) for e in w["exercises"]]} for w in t["workouts"]]}
        )
        for t in _TEMPLATES
    ]


def get_template(conn: Connection, template_id: str) -> ProgramTemplate | None:
    return next((t for t in templates(conn) if t.id == template_id), None)
