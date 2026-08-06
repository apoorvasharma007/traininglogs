from __future__ import annotations

import datetime
import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from traininglogs.agent.reps import parse_reps
from traininglogs.models.models import (
    Exercise,
    Goal,
    SessionCooldown,
    SessionWarmup,
    WarmupSet,
    WorkingSet,
)


def _validate_date(v: str) -> str:
    if not isinstance(v, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        raise ValueError("Date must be formatted as YYYY-MM-DD")
    try:
        datetime.datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Date is not a valid calendar date: {v}")
    return v


class TrainingLogLLMExtract(BaseModel):
    date: str
    program: Optional[str] = None
    phase: Optional[int] = None
    week: Optional[int] = None
    is_deload_week: Optional[bool] = None
    focus: Optional[str] = None
    session_duration_minutes: Optional[int] = None
    warmup: Optional[List[SessionWarmup]] = None
    exercises: List[Exercise]
    cooldown: Optional[List[SessionCooldown]] = None
    notes: Optional[str] = None
    uncertain_fields: List[str] = Field(default_factory=list)
    # Deterministic drop-check findings (exercise-count mismatch, orphaned RPE/weight-shaped
    # tokens) — distinct from uncertain_fields, which is the LLM's own self-reported doubt
    # about a field it did extract. A warning means "we think this is actually wrong."
    warnings: List[str] = Field(default_factory=list)

    @field_validator("date")
    @classmethod
    def valid_date(cls, v: str) -> str:
        return _validate_date(v)


class SessionShellExtract(BaseModel):
    """Everything a TrainingLogLLMExtract has except `exercises` — the session-level call
    in the split extraction flow. A separate call per exercise fills in `exercises`."""

    date: str
    program: Optional[str] = None
    phase: Optional[int] = None
    week: Optional[int] = None
    is_deload_week: Optional[bool] = None
    focus: Optional[str] = None
    session_duration_minutes: Optional[int] = None
    warmup: Optional[List[SessionWarmup]] = None
    cooldown: Optional[List[SessionCooldown]] = None
    notes: Optional[str] = None
    # Optional for the same reason as ExerciseExtract.uncertain_fields -- see the note there.
    uncertain_fields: Optional[List[str]] = Field(default_factory=list)

    @field_validator("uncertain_fields", mode="before")
    @classmethod
    def null_means_none_uncertain(cls, v: object) -> object:
        return [] if v is None else v

    @field_validator("date")
    @classmethod
    def valid_date(cls, v: str) -> str:
        return _validate_date(v)


class SetExtract(BaseModel):
    """One set, as the person wrote it.

    The model's job here is to find a set and copy it. Converting what it copied is Python's
    job (see agent/reps.py) — that split exists because copying is what a language model does
    reliably and `source_line` can prove it did so, while turning "8+1" into {full: 8,
    partial: 1} is string handling that should behave identically every time.

    Working sets and warmup sets use this same shape. They used to differ — `rep_count` was an
    object on one and a plain integer on the other — which cost a rule in the prompt and gave
    the model something else to get wrong."""

    number: int = Field(description="Position of this set within the exercise, starting at 1.")
    source_line: str = Field(
        description=(
            "The exact line of text this set was read from, character for character. Do not "
            "tidy it, renumber it, or shorten it."
        )
    )
    weight_kg: Optional[float] = Field(
        default=None,
        description=(
            "Weight in kilograms. Convert if the text says lbs. Omit for bodyweight work or "
            "when no weight is written."
        ),
    )
    reps: Optional[str] = Field(
        default=None,
        description=(
            "Rep information exactly as written — '8', '8+1', 'left 8, right 7', "
            "'12 catches', 'feel'. Do not convert it to a number. Omit if the set records no "
            "reps at all, such as a timed hold."
        ),
    )
    rpe: Optional[float] = Field(
        default=None,
        description="Rate of perceived exertion, 1-10 in whole or half steps. Omit if not stated.",
    )
    duration_seconds: Optional[int] = Field(
        default=None, description="Duration in seconds for a timed set, e.g. a 20s hold."
    )
    distance_meters: Optional[float] = Field(
        default=None, description="Distance in metres, if the set records one."
    )
    notes: Optional[str] = Field(
        default=None,
        description=(
            "Commentary about this set specifically — how it felt, a form cue, a correction. "
            "Not a restatement of its own weight, reps or RPE."
        ),
    )

    @field_validator("number")
    @classmethod
    def number_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Set number must be positive")
        return v


class ExerciseExtract(BaseModel):
    """One worker call's result — the shape the model is asked to fill.

    Deliberately NOT inheriting from Exercise. It used to, which meant the model was handed the
    production model behind the exercises/working_sets tables: 16 fields, six levels of nesting.
    Production extraction teams measure that as costly — 55% of their accuracy improvements came
    from flattening schemas "so the model never had to infer a relationship", and 4+ levels of
    nesting degrades quality outright. See `extraction-design-principles.md`.

    So the shapes are separate. This one is built for a model to fill; `to_exercise()` projects
    it onto the production model, which is unchanged. No DB, API or dashboard change.

    Not asked for, and why: `tags`, `modality`, `movement_pattern`, `target_muscle_groups`,
    `rep_tempo`, `current_goal`, `form_cues` are classifications rather than content. Dropping
    them improves accuracy on what remains, and nothing is lost — the raw text is kept, so they
    can be backfilled later by a separate classification pass. This schema carries what the
    person wrote; classifying it is a different job.

    Flat at the top level rather than nested under a wrapper key: live testing showed
    tool-calling models flatten a single-nested-object schema regardless of prompt wording, so
    matching that tendency is more robust than fighting it."""

    # No `number` field, deliberately. The splitter already established this exercise's position
    # and assemble() overwrites whatever a worker reports with it, so asking for it gave the
    # model one more thing to get wrong in exchange for nothing. Removed 2026-08-06, after a run
    # where the single most common failure was a worker returning `{"number": 1}` and nothing
    # else -- filling the one field that gets discarded.
    name: str = Field(description="The exercise's name, as written.")
    sets: Optional[List[SetExtract]] = Field(
        default=None, description="The exercise's working sets, in the order they appear."
    )
    warmup_sets: Optional[List[SetExtract]] = Field(
        default=None,
        description="Warmup sets for this exercise, in order. Same shape as working sets.",
    )
    notes: Optional[str] = Field(
        default=None,
        description=(
            "Commentary about the exercise as a whole — anything not specific to one set."
        ),
    )
    warmup_notes: Optional[str] = Field(
        default=None,
        description=(
            "Commentary about the warmup as a whole. Not a restatement of the warmup sets' own "
            "weights or reps."
        ),
    )
    # Optional rather than a plain list because models naturally serialise "nothing uncertain"
    # as null, and a schema that only accepts an array gets the whole tool call rejected for it.
    # On 2026-08-06 that discarded two complete, correct extractions out of 22 exercises —
    # Groq returned `"uncertain_fields": null` and its validator refused the call. Research
    # finding 5 in extraction-design-principles.md says the same thing more generally: requiring
    # a field that may legitimately be absent makes models behave worse, not better.
    uncertain_fields: Optional[List[str]] = Field(
        default_factory=list,
        description=(
            "Dot-paths, relative to this exercise, that you are not confident about — e.g. "
            "'sets.2.rpe'. Only list fields you actually filled in. Omit or use null if none."
        ),
    )

    @field_validator("uncertain_fields", mode="before")
    @classmethod
    def null_means_none_uncertain(cls, v: object) -> object:
        return [] if v is None else v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Exercise name cannot be empty")
        return v

    @model_validator(mode="after")
    def must_contain_at_least_one_set(self) -> "ExerciseExtract":
        """An exercise with no sets at all is a non-answer, not a result.

        Every field except `name` is optional, which is right — a model shouldn't invent an RPE
        it can't see. But that also means `{"name": "Leg Extension"}` satisfies the schema while
        carrying none of the data the call exists to collect, and none of the other checks can
        see it: check_sources_are_real() and check_sets_are_numbered_and_sourced() both iterate
        over the sets that came back, so zero sets means zero findings.

        Failing here instead routes it through the provider's retry, which re-asks with the
        reason. Only if every attempt comes back empty does it become a flagged placeholder —
        visible, rather than a session that looks clean with its sets quietly missing."""
        if not (self.sets or self.warmup_sets):
            raise ValueError(
                f"Exercise {self.name!r} has no working sets and no warmup sets. If the text "
                "really records none, say so in notes; otherwise read the sets from the text."
            )
        return self

    @field_validator("sets", "warmup_sets", mode="before")
    @classmethod
    def drop_nulls_in_lists(cls, v: object) -> object:
        # Tool-calling models occasionally emit a null entry inside a list.
        if isinstance(v, list):
            return [x for x in v if x is not None]
        return v

    def to_exercise(self, number: int) -> tuple[Exercise, List[str]]:
        """Project onto the production model, converting rep text to typed counts.

        `number` comes from the caller because the splitter is what knows this exercise's
        position in the session; the worker only ever saw its own excerpt.

        Returns the Exercise and any warnings raised while converting — rep text that could not
        be read is left unset and reported rather than guessed at. The classification fields
        this schema does not ask for are left unset: deferred, not lost."""
        warnings: List[str] = []

        def _working(s: SetExtract) -> WorkingSet:
            parsed = parse_reps(s.reps)
            if parsed.warning:
                warnings.append(f"set {s.number}: {parsed.warning}")
            return WorkingSet(
                number=s.number,
                weight_kg=s.weight_kg,
                rep_count=parsed.rep_count,
                unilateral_rep_count=parsed.unilateral,
                rpe=s.rpe,
                duration_seconds=s.duration_seconds,
                distance_meters=s.distance_meters,
                notes=s.notes,
            )

        def _warmup(s: SetExtract) -> WarmupSet:
            parsed = parse_reps(s.reps)
            if parsed.warning:
                warnings.append(f"warmup {s.number}: {parsed.warning}")
            # WarmupSet's rep_count is a plain integer and its weight is required; a warmup set
            # with no weight written is recorded as 0, which is what bodyweight warmups mean.
            return WarmupSet(
                number=s.number,
                weight_kg=s.weight_kg if s.weight_kg is not None else 0.0,
                rep_count=parsed.rep_count.full if parsed.rep_count else None,
                notes=s.notes,
            )

        exercise = Exercise(
            number=number,
            name=self.name,
            sets=[_working(s) for s in self.sets] if self.sets else None,
            warmup_sets=[_warmup(s) for s in self.warmup_sets] if self.warmup_sets else None,
            notes=self.notes,
            warmup_notes=self.warmup_notes,
        )
        return exercise, warnings


class ExercisePosition(BaseModel):
    """One entry in the splitter's ordered exercise listing. `anchor` is a verbatim quote used
    to deterministically locate this exercise's text in the source document (see
    extraction._chunk_exercises) — deliberately separate from `name`, which is the cleaned,
    canonical label and is NOT guaranteed to appear literally in the source text."""

    position: int
    name: str
    anchor: str

    @field_validator("position")
    @classmethod
    def position_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Position must be positive")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Exercise name cannot be empty")
        return v

    @field_validator("anchor")
    @classmethod
    def anchor_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Anchor cannot be empty")
        return v


class ExerciseSplit(BaseModel):
    """The splitter call's result: how many exercises the session has, and their names, in
    order. Workers are told "extract the Nth exercise" using this list's positions."""

    exercises: List[ExercisePosition]


class LLMParserError(Exception):
    pass
