from __future__ import annotations

from dataclasses import dataclass, field

NOTE_PREVIEW_CHARS = 40


@dataclass
class NotePreview:
    full_text: str
    max_chars: int = NOTE_PREVIEW_CHARS

    @property
    def display(self) -> str:
        if len(self.full_text) <= self.max_chars:
            return self.full_text
        return self.full_text[:self.max_chars].rstrip() + "..."


@dataclass
class GoalSummary:
    weight_kg: float | None = None
    sets: int | None = None
    rep_range_min: int | None = None
    rep_range_max: int | None = None
    rest_minutes: int | None = None
    rest_seconds: int | None = None
    distance_meters: float | None = None
    target_duration_seconds: int | None = None


@dataclass
class SessionHeader:
    date: str
    program: str | None = None
    phase: int | None = None
    week: int | None = None
    focus: str | None = None
    duration_minutes: int | None = None
    uncertain_fields: frozenset[str] = field(default_factory=frozenset)


@dataclass
class WarmupRow:
    number: int
    weight_kg: float
    rep_count: int | None = None
    notes: str | None = None
    uncertain_fields: frozenset[str] = field(default_factory=frozenset)


@dataclass
class WorkingSetRow:
    number: int
    # strength
    weight_kg: float | None = None
    reps: str | None = None  # "12", "8+1" (full+partial), "8L / 8R" (unilateral)
    rpe: float | None = None
    quality: str | None = None  # RepQualityAssessment value string
    failure_technique: str | None = None  # human-readable summary
    # activity
    duration_seconds: int | None = None
    distance_meters: float | None = None
    heart_rate_bpm: int | None = None
    # common
    notes: str | None = None
    uncertain_fields: frozenset[str] = field(default_factory=frozenset)


@dataclass
class ExerciseHeader:
    number: int
    name: str
    goal: GoalSummary | None = None
    uncertain_fields: frozenset[str] = field(default_factory=frozenset)


@dataclass
class ExerciseCard:
    header: ExerciseHeader
    warmup_rows: list[WarmupRow] = field(default_factory=list)
    working_set_rows: list[WorkingSetRow] = field(default_factory=list)
    note_preview: NotePreview | None = None
    warmup_note_preview: NotePreview | None = None


@dataclass
class UserValidationCard:
    session_header: SessionHeader
    exercises: list[ExerciseCard] = field(default_factory=list)
