from __future__ import annotations

from datetime import date
from typing import Any, Optional

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
    source_kind: str = "markdown"
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
