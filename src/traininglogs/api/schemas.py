from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from traininglogs.agent.card_edits import CardEdit, CardOp


class SessionSummary(BaseModel):
    session_id: str
    date: date
    program: Optional[str]
    phase: Optional[int]
    week: Optional[int]
    focus: Optional[str]
    duration_minutes: Optional[int]
    is_deload_week: Optional[bool]
    weight_unit: str
    exercises: list[str] = Field(default_factory=list, description="Exercise names, in order.")


class MovementOut(BaseModel):
    number: int
    name: str
    reps: Optional[int]
    duration_seconds: Optional[int]
    notes: Optional[str]


class WarmupSetOut(BaseModel):
    number: int
    weight_kg: Optional[float]
    rep_count: Optional[int]
    notes: Optional[str]


class WorkingSetOut(BaseModel):
    number: int
    weight_kg: Optional[float]
    reps_full: Optional[int]
    reps_partial: Optional[int]
    left_reps_full: Optional[int]
    left_reps_partial: Optional[int]
    right_reps_full: Optional[int]
    right_reps_partial: Optional[int]
    rpe: Optional[float]
    rep_quality: Optional[str]
    rest_minutes: Optional[float]
    rest_seconds: Optional[int]
    duration_seconds: Optional[int]
    distance_meters: Optional[float]
    heart_rate_bpm: Optional[int]
    notes: Optional[str]
    failure_technique: Optional[Any]


class ExerciseOut(BaseModel):
    number: int
    name: str
    tags: Optional[list[str]]
    modality: Optional[str]
    movement_pattern: Optional[list[str]]
    notes: Optional[str]
    warmup_notes: Optional[str]
    form_cues: Optional[list[str]]
    goal_weight_kg: Optional[float]
    goal_sets: Optional[int]
    goal_rep_min: Optional[int]
    goal_rep_max: Optional[int]
    goal_rest_min: Optional[int]
    goal_rest_seconds: Optional[int]
    goal_distance_meters: Optional[float]
    goal_target_duration_sec: Optional[int]
    target_muscle_groups: Optional[list[str]]
    rep_tempo: Optional[str]
    sets: list[WorkingSetOut] = []
    warmup_sets: list[WarmupSetOut] = []


class SessionDetail(BaseModel):
    session_id: str
    date: date
    program: Optional[str]
    program_author: Optional[str]
    program_length_weeks: Optional[int]
    phase: Optional[int]
    week: Optional[int]
    is_deload_week: Optional[bool]
    focus: Optional[str]
    duration_minutes: Optional[int]
    weight_unit: str
    user_id: Optional[str]
    user_name: Optional[str]
    source_file: Optional[str]
    notes: Optional[str] = None
    warmup: list[MovementOut] = []
    cooldown: list[MovementOut] = []
    exercises: list[ExerciseOut] = []


class CaptureIn(BaseModel):
    content: str = Field(min_length=1, description="The session text, as written.")
    source_kind: Literal["text"] = Field(
        default="text", description="Always text: this endpoint is for notes the model reads."
    )
    source_file: Optional[str] = None


class CaptureOut(BaseModel):
    raw_input_id: str
    extraction_id: Optional[str] = None
    error: Optional[str] = None


class ConfirmIn(BaseModel):
    extract: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "The final extract to write, if it differs from the extraction's own stored "
            "reading -- e.g. after one or more /correct calls. Omit to accept the reading "
            "as-is."
        ),
    )
    corrections: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="The corrections that produced `extract`, recorded alongside the "
        "extraction. Omit if none were applied.",
    )
    program_workout_id: Optional[str] = Field(
        default=None,
        description="The planned workout this session counts as, so the program moves on to "
        "the next one. Omit when it isn't part of a program.",
    )


class ConfirmOut(BaseModel):
    session_id: str


class CorrectIn(BaseModel):
    extract: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "The extract to correct, if it differs from the extraction's own stored reading "
            "-- the `extract` field from a prior /correct call, when applying a second "
            "correction on top of the first. Omit on the first correction."
        ),
    )
    instruction: str = Field(min_length=1, description="What's wrong, in plain language.")


class CorrectOut(BaseModel):
    """Returned by both /correct and /edit, so a client handles either reply the same way."""

    extract: dict[str, Any] = Field(
        description="The corrected extract, in full -- round-trip this back as `extract` on "
        "the next /correct or /edit call, or as `extract` on /confirm once done."
    )
    card: dict[str, Any] = Field(description="The same state, rendered as a card for display.")
    correction: dict[str, Any] = Field(
        description="{at, source, edits} plus `instruction` when source is \"ai\", or `op` "
        "and `path` for an add/remove -- accumulate these into a list to pass as "
        "`corrections` on /confirm."
    )
    created_path: Optional[str] = Field(
        default=None,
        description="The new line's path after an add (/edit with `op`), so the client can open "
        "it for editing; null otherwise.",
    )


class EditIn(BaseModel):
    extract: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "The extract to edit, if it differs from the extraction's own stored reading -- "
            "the `extract` from a prior /correct or /edit call. Omit on the first change."
        ),
    )
    edits: list[CardEdit] = Field(
        default_factory=list,
        description="Values changed on the card: each card element's own `path`, the card "
        "field name, and the new value. An empty string clears a value.",
    )
    op: Optional[CardOp] = Field(
        default=None,
        description="Add or remove one line instead: `add_set`, `add_warmup_set`, "
        "`add_exercise` or `remove`, on the `path` of the line it applies to.",
    )

    @model_validator(mode="after")
    def edits_or_op(self) -> EditIn:
        if bool(self.edits) == (self.op is not None):
            raise ValueError("send either `edits` or `op`, exactly one")
        return self


class ExerciseHistoryRow(BaseModel):
    date: date
    phase: Optional[int]
    week: Optional[int]
    session_id: str
    number: int
    weight_kg: Optional[float]
    reps_full: Optional[int]
    reps_partial: Optional[int]
    rpe: Optional[float]
    rep_quality: Optional[str]
    failure_technique: Optional[Any]


class LiftSummary(BaseModel):
    name: str
    measure: Literal["estimated_max", "bodyweight_reps"]
    sessions: int
    latest: Optional[float]
    best: Optional[float]
    last_date: Optional[date]
    trend: Optional[Literal["up", "flat", "down"]]


class LiftsOut(BaseModel):
    key_lifts: list[LiftSummary]
    other_lifts: list[LiftSummary]


class LiftSet(BaseModel):
    number: int
    weight_kg: Optional[float]
    reps_full: Optional[int]
    left_reps_full: Optional[int]
    right_reps_full: Optional[int]
    rpe: Optional[float]


class LiftBestSet(BaseModel):
    number: int
    weight_kg: Optional[float]
    reps: Optional[int]
    rpe: Optional[float]


class LiftPoint(BaseModel):
    session_id: str
    date: date
    value: Optional[float] = Field(
        description="Best estimated max (kg), or best reps at bodyweight; null for a bodyweight "
        "lift's session with only weighted sets"
    )
    method: Optional[Literal["rpe"]]
    heaviest_kg: Optional[float]
    goal_weight_kg: Optional[float]
    records: list[str]
    best_set: LiftBestSet
    sets: list[LiftSet]


class LiftDetail(LiftSummary):
    points: list[LiftPoint]


class PlanExercise(BaseModel):
    """One exercise in a workout's plan: how many sets and the target reps. No weights."""

    name: str = Field(min_length=1)
    warmup_sets: int = Field(default=0, ge=0, le=20)
    working_sets: int = Field(default=1, ge=0, le=20)
    target_reps: Optional[int] = Field(default=None, gt=0, le=100)
    amrap: bool = Field(default=False, description="As many reps as you can.")
    alternatives: list[str] = Field(
        default_factory=list,
        description="Other exercises that can take this one's place. A workout starts with the "
        "first; the session can switch to an alternative.",
    )

    @model_validator(mode="after")
    def strip_name(self) -> PlanExercise:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name can't be blank")
        # Blank, repeated, or the same as the name (ignoring case): dropped.
        seen = {self.name.lower()}
        kept = []
        for alt in (a.strip() for a in self.alternatives):
            if alt and alt.lower() not in seen:
                seen.add(alt.lower())
                kept.append(alt)
        self.alternatives = kept
        return self


class Movement(BaseModel):
    """A warm-up or cool-down movement: reps, a duration, or neither ("easy walk")."""

    name: str = Field(min_length=1)
    reps: Optional[int] = Field(default=None, ge=0, le=1000)
    duration_seconds: Optional[int] = Field(default=None, ge=0, le=86400)

    @model_validator(mode="after")
    def strip_name(self) -> Movement:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name can't be blank")
        return self


class WorkoutOut(BaseModel):
    id: str
    position: int
    name: Optional[str]
    last_done: Optional[date]
    exercises: list[PlanExercise]
    warmup: list[Movement] = []
    cooldown: list[Movement] = []


class TemplateWorkout(BaseModel):
    name: str
    exercises: list[PlanExercise]


class ProgramTemplate(BaseModel):
    """A ready-made program to copy into your own programs."""

    id: str
    name: str
    days: str = Field(description='How often it is run, e.g. "3 days a week".')
    workouts: list[TemplateWorkout]


class WorkoutMovementsIn(BaseModel):
    warmup: list[Movement] = []
    cooldown: list[Movement] = []


class DeloadStatus(BaseModel):
    days_since: int = Field(description="Days of training counted toward the next deload.")
    due: bool = Field(description="days_since has reached the program's deload_after_days.")
    in_progress: int = Field(description="How many of the latest sessions in a row were deloads.")


class ProgramOut(BaseModel):
    id: str
    name: str
    deload_after_days: int
    following: bool
    following_since: Optional[date]
    workouts: list[WorkoutOut]
    next_workout_id: Optional[str] = Field(
        description="The workout after the one in the program's latest session; workout 1 when "
        "there is none or after the last. Null when the program has no workouts."
    )
    deload: DeloadStatus


class ProgramIn(BaseModel):
    name: str = Field(min_length=1)


class ProgramPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    deload_after_days: Optional[int] = Field(default=None, gt=0, le=365)


class WorkoutIn(BaseModel):
    name: Optional[str] = None


class WorkoutOrderIn(BaseModel):
    workout_ids: list[str] = Field(description="Every workout of the program, once each, in the new order.")


class WorkoutExercisesIn(BaseModel):
    exercises: list[PlanExercise]


class PinIn(BaseModel):
    note: str = Field(min_length=1)


class PinOut(BaseModel):
    name_key: str
    note: str
    pinned_at: Any


class ManualWarmupSet(BaseModel):
    weight_kg: float = Field(ge=0)
    reps: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class ManualSet(BaseModel):
    weight_kg: Optional[float] = Field(default=None, ge=0)
    reps: Optional[int] = Field(default=None, ge=0)
    rpe: Optional[float] = None
    notes: Optional[str] = None


class ManualExercise(BaseModel):
    name: str = Field(min_length=1)
    notes: Optional[str] = None
    warmup_sets: list[ManualWarmupSet] = []
    sets: list[ManualSet] = []

    @model_validator(mode="after")
    def has_a_set(self) -> ManualExercise:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("an exercise needs a name")
        if not self.warmup_sets and not self.sets:
            raise ValueError(f"{self.name} has no sets")
        return self


class ManualMovement(Movement):
    notes: Optional[str] = None


class ManualSessionIn(BaseModel):
    """A session entered set by set in the app. Only the sets the person ticked are sent."""

    client_id: str = Field(
        pattern=r"^[0-9a-f]{32}$",
        description="Made by the phone when the session starts. Sending the same session again "
        "returns the one already saved.",
    )
    date: date
    focus: Optional[str] = Field(default=None, description="What History shows as its title, e.g. \"1 · Bench\".")
    duration_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    program_workout_id: Optional[str] = None
    is_deload: bool = False
    notes: Optional[str] = None
    warmup: list[ManualMovement] = []
    cooldown: list[ManualMovement] = []
    exercises: list[ManualExercise] = Field(min_length=1)


class SessionSaved(BaseModel):
    session_id: str
    created: bool = Field(description="False when this session had already been saved.")


class LastSet(BaseModel):
    weight_kg: Optional[float]
    reps: Optional[int]
    rpe: Optional[float] = None
    notes: Optional[str]


class LastExercise(BaseModel):
    """The most recent session that had this exercise, whatever program it was in."""

    name: str
    date: date
    session_id: str
    notes: Optional[str]
    warmup_sets: list[LastSet]
    sets: list[LastSet]
