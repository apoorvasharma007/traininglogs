from __future__ import annotations

from traininglogs.agent.extraction import PLACEHOLDER_NOTE_PREFIX
from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.agent.validation_card_data import (
    ExerciseCard,
    ExerciseHeader,
    GoalSummary,
    MovementRow,
    NotePreview,
    SessionHeader,
    SessionMovementSection,
    UserValidationCard,
    WarmupRow,
    WorkingSetRow,
)
from traininglogs.models.models import (
    DropSetTechnique,
    Exercise,
    Goal,
    LLPTechnique,
    MyoRepsTechnique,
    RepCount,
    StaticTechnique,
    UnilateralReps,
    WorkingSet,
)

_SESSION_FIELDS = frozenset(
    {"date", "focus", "program", "phase", "week", "is_deload_week", "session_duration_minutes"}
)
_SESSION_FIELD_RENAME = {"session_duration_minutes": "duration_minutes"}


class ValidationCardBuilder:
    def build(self, extract: TrainingLogLLMExtract) -> UserValidationCard:
        uncertain = set(extract.uncertain_fields)
        return UserValidationCard(
            session_header=self._session_header(extract, uncertain),
            warmup_section=self._movement_section("Warmup", extract.warmup),
            exercises=[
                self._exercise_card(ex, idx, uncertain)
                for idx, ex in enumerate(extract.exercises)
            ],
            cooldown_section=self._movement_section("Cooldown", extract.cooldown),
            note_preview=NotePreview(extract.notes) if extract.notes else None,
            warnings=list(extract.warnings),
        )

    def _session_header(
        self, extract: TrainingLogLLMExtract, uncertain: set[str]
    ) -> SessionHeader:
        uf: set[str] = set()
        for path in uncertain:
            parts = path.split(".")
            if len(parts) == 1 and parts[0] in _SESSION_FIELDS:
                uf.add(_SESSION_FIELD_RENAME.get(parts[0], parts[0]))
        return SessionHeader(
            date=extract.date,
            program=extract.program,
            phase=extract.phase,
            week=extract.week,
            is_deload_week=extract.is_deload_week,
            focus=extract.focus,
            duration_minutes=extract.session_duration_minutes,
            uncertain_fields=frozenset(uf),
        )

    def _movement_section(self, title: str, movements) -> SessionMovementSection | None:
        if not movements:
            return None
        return SessionMovementSection(
            title=title,
            movements=[
                MovementRow(
                    number=m.number,
                    name=m.name,
                    reps=m.reps,
                    duration_seconds=m.duration_seconds,
                    notes=m.notes,
                )
                for m in movements
            ],
        )

    def _exercise_card(
        self, ex: Exercise, ex_idx: int, uncertain: set[str]
    ) -> ExerciseCard:
        ex_prefix = f"exercises.{ex_idx}."
        header_uf: set[str] = set()
        for path in uncertain:
            if path.startswith(ex_prefix):
                remainder = path[len(ex_prefix):]
                parts = remainder.split(".")
                if len(parts) == 1 and parts[0] == "name":
                    header_uf.add(parts[0])

        failed = bool(ex.notes and ex.notes.startswith(PLACEHOLDER_NOTE_PREFIX))

        return ExerciseCard(
            header=ExerciseHeader(
                number=ex.number,
                name=ex.name,
                goal=self._goal_summary(ex.current_goal) if ex.current_goal else None,
                uncertain_fields=frozenset(header_uf),
                failed=failed,
            ),
            warmup_rows=self._warmup_rows(ex, ex_idx, uncertain),
            working_set_rows=self._working_set_rows(ex, ex_idx, uncertain),
            note_preview=NotePreview(ex.notes) if ex.notes and not failed else None,
            warmup_note_preview=NotePreview(ex.warmup_notes) if ex.warmup_notes else None,
            failure_reason=ex.notes if failed else None,
        )

    def _goal_summary(self, goal: Goal) -> GoalSummary:
        return GoalSummary(
            weight_kg=goal.weight_kg,
            sets=goal.sets,
            rep_range_min=goal.rep_range.min if goal.rep_range else None,
            rep_range_max=goal.rep_range.max if goal.rep_range else None,
            rest_minutes=goal.rest.minutes if goal.rest else None,
            rest_seconds=goal.rest.seconds if goal.rest else None,
            distance_meters=goal.distance_meters,
            target_duration_seconds=goal.target_duration_seconds,
        )

    def _warmup_rows(
        self, ex: Exercise, ex_idx: int, uncertain: set[str]
    ) -> list[WarmupRow]:
        if not ex.warmup_sets:
            return []
        rows = []
        for ws_idx, ws in enumerate(ex.warmup_sets):
            uf = self._set_uncertain(uncertain, ex_idx, "warmup_sets", ws_idx)
            rows.append(
                WarmupRow(
                    number=ws.number,
                    weight_kg=ws.weight_kg,
                    rep_count=ws.rep_count,
                    notes=ws.notes,
                    uncertain_fields=frozenset(uf),
                )
            )
        return rows

    def _working_set_rows(
        self, ex: Exercise, ex_idx: int, uncertain: set[str]
    ) -> list[WorkingSetRow]:
        if not ex.sets:
            return []
        rows = []
        for s_idx, s in enumerate(ex.sets):
            uf = self._set_uncertain(uncertain, ex_idx, "sets", s_idx)
            rows.append(self._working_set_row(s, uf))
        return rows

    def _set_uncertain(
        self, uncertain: set[str], ex_idx: int, set_key: str, set_idx: int
    ) -> set[str]:
        prefix = f"exercises.{ex_idx}.{set_key}.{set_idx}."
        return {path[len(prefix):].split(".")[0] for path in uncertain if path.startswith(prefix)}

    def _working_set_row(self, s: WorkingSet, uf: set[str]) -> WorkingSetRow:
        return WorkingSetRow(
            number=s.number,
            weight_kg=s.weight_kg,
            reps=self._fmt_reps(s.rep_count, s.unilateral_rep_count),
            rpe=s.rpe,
            quality=s.rep_quality_assessment.value if s.rep_quality_assessment else None,
            failure_technique=self._fmt_failure(s.failure_technique) if s.failure_technique else None,
            duration_seconds=s.duration_seconds,
            distance_meters=s.distance_meters,
            heart_rate_bpm=s.heart_rate_bpm,
            notes=s.notes,
            uncertain_fields=frozenset(uf),
        )

    def _fmt_reps(
        self,
        rep_count: RepCount | None,
        unilateral: UnilateralReps | None,
    ) -> str | None:
        if unilateral is not None:
            parts: list[str] = []
            if unilateral.left:
                if unilateral.left.partial:
                    parts.append(f"{unilateral.left.full}+{unilateral.left.partial}L")
                else:
                    parts.append(f"{unilateral.left.full}L")
            if unilateral.right:
                if unilateral.right.partial:
                    parts.append(f"{unilateral.right.full}+{unilateral.right.partial}R")
                else:
                    parts.append(f"{unilateral.right.full}R")
            return " / ".join(parts) if parts else None
        if rep_count is not None:
            if rep_count.partial:
                return f"{rep_count.full}+{rep_count.partial}"
            return str(rep_count.full)
        return None

    def _fmt_failure(self, technique: object) -> str:
        if isinstance(technique, LLPTechnique):
            return f"LLP ({technique.details.partial_rep_count} partials)"
        if isinstance(technique, StaticTechnique):
            return f"Static Hold ({technique.details.hold_duration_seconds}s)"
        if isinstance(technique, MyoRepsTechnique):
            return f"Myo-reps ({len(technique.details.mini_sets)} mini-sets)"
        if isinstance(technique, DropSetTechnique):
            return f"Drop set ({len(technique.details.drop_sets)} drops)"
        return str(technique)
