"""Ready-made programs to copy from. Kept in code while there are a few starter ones; a larger
collection would move to the database, behind the same /templates calls."""
from __future__ import annotations

from traininglogs.api.schemas import PlanExercise, ProgramTemplate, TemplateWorkout


def _ex(name: str, sets: int, reps: int | None, warmup: int = 0, alternatives: tuple[str, ...] = ()) -> PlanExercise:
    """reps None means as many as you can."""
    return PlanExercise(
        name=name, warmup_sets=warmup, working_sets=sets, target_reps=reps, amrap=reps is None,
        alternatives=list(alternatives),
    )


def _workout(name: str, *exercises: PlanExercise) -> TemplateWorkout:
    return TemplateWorkout(name=name, exercises=list(exercises))


_PUSH = _workout(
    "Push",
    _ex("Bench press", 4, 6, warmup=2),
    _ex("Overhead press", 3, 8, warmup=2),
    _ex("Incline dumbbell press", 3, 10),
    _ex("Lateral raise", 3, 12),
    _ex("Triceps pushdown", 3, 12),
)
_PULL = _workout(
    "Pull",
    _ex("Deadlift", 3, 5, warmup=2),
    _ex("Pull-up", 3, None, alternatives=("Lat pulldown",)),
    _ex("Barbell row", 3, 8, warmup=2),
    _ex("Face pull", 3, 15),
    _ex("Biceps curl", 3, 12),
)
_LEGS = _workout(
    "Legs",
    _ex("Squat", 4, 6, warmup=2),
    _ex("Romanian deadlift", 3, 8, warmup=2),
    _ex("Leg press", 3, 10),
    _ex("Leg curl", 3, 12),
    _ex("Calf raise", 3, 15),
)
_UPPER_A = _workout(
    "Upper A",
    _ex("Bench press", 4, 6, warmup=2),
    _ex("Barbell row", 4, 6, warmup=2),
    _ex("Overhead press", 3, 8, warmup=2),
    _ex("Lat pulldown", 3, 10),
    _ex("Biceps curl", 3, 12),
)
_LOWER_A = _workout(
    "Lower A",
    _ex("Squat", 4, 6, warmup=2),
    _ex("Romanian deadlift", 3, 8, warmup=2),
    _ex("Leg press", 3, 10),
    _ex("Calf raise", 3, 15),
)

TEMPLATES: list[ProgramTemplate] = [
    ProgramTemplate(
        id="5x5-strength", name="5×5 strength", days="3 days a week",
        workouts=[
            _workout("A", _ex("Squat", 5, 5, warmup=2), _ex("Bench press", 5, 5, warmup=2), _ex("Barbell row", 5, 5, warmup=2)),
            _workout("B", _ex("Squat", 5, 5, warmup=2), _ex("Overhead press", 5, 5, warmup=2), _ex("Deadlift", 1, 5, warmup=2)),
        ],
    ),
    ProgramTemplate(id="push-pull-legs", name="Push / pull / legs", days="3 or 6 days a week", workouts=[_PUSH, _PULL, _LEGS]),
    ProgramTemplate(
        id="upper-lower", name="Upper / lower", days="4 days a week",
        workouts=[
            _UPPER_A,
            _LOWER_A,
            _workout(
                "Upper B",
                _ex("Overhead press", 4, 6, warmup=2),
                _ex("Pull-up", 4, None, alternatives=("Lat pulldown",)),
                _ex("Incline dumbbell press", 3, 10),
                _ex("Cable row", 3, 10),
                _ex("Triceps pushdown", 3, 12),
            ),
            _workout(
                "Lower B",
                _ex("Deadlift", 3, 5, warmup=2),
                _ex("Front squat", 3, 8, warmup=2),
                _ex("Walking lunge", 3, 10),
                _ex("Leg curl", 3, 12),
            ),
        ],
    ),
    ProgramTemplate(
        id="upper-lower-ppl", name="Upper / lower / PPL", days="5 days a week",
        workouts=[_UPPER_A.model_copy(update={"name": "Upper"}), _LOWER_A.model_copy(update={"name": "Lower"}), _PUSH, _PULL, _LEGS],
    ),
]


def get_template(template_id: str) -> ProgramTemplate | None:
    return next((t for t in TEMPLATES if t.id == template_id), None)
