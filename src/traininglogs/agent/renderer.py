from __future__ import annotations

from rich.console import Console

from traininglogs.agent.card import (
    ConfirmationCard,
    ExerciseCard,
    ExerciseHeader,
    GoalSummary,
    NotePreview,
    SessionHeader,
    WarmupRow,
    WorkingSetRow,
)


def _mark(value: str, field_name: str, uncertain_fields: frozenset[str]) -> str:
    if field_name in uncertain_fields:
        return f"[yellow]{value}?[/yellow]"
    return value


def _fmt_goal(goal: GoalSummary) -> str:
    parts: list[str] = []
    if goal.weight_kg is not None:
        parts.append(f"{goal.weight_kg:g} kg")
    if goal.sets is not None:
        parts.append(f"{goal.sets} sets")
    if goal.rep_range_min is not None and goal.rep_range_max is not None:
        parts.append(f"{goal.rep_range_min}–{goal.rep_range_max} reps")
    elif goal.rep_range_min is not None:
        parts.append(f"{goal.rep_range_min}+ reps")
    if goal.distance_meters is not None:
        parts.append(f"{goal.distance_meters:g} m")
    if goal.target_duration_seconds is not None:
        mins, secs = divmod(goal.target_duration_seconds, 60)
        parts.append(f"{mins}:{secs:02d}")
    if goal.rest_minutes is not None:
        parts.append(f"{goal.rest_minutes} min rest")
    if goal.rest_seconds is not None:
        parts.append(f"{goal.rest_seconds}s rest")
    return "  |  ".join(parts)


def _fmt_working_set(row: WorkingSetRow) -> str:
    parts: list[str] = []

    if row.weight_kg is not None or row.reps is not None:
        weight = (
            _mark(f"{row.weight_kg:g} kg", "weight_kg", row.uncertain_fields)
            if row.weight_kg is not None
            else ""
        )
        reps = (
            _mark(row.reps, "reps", row.uncertain_fields)
            if row.reps is not None
            else ""
        )
        if weight and reps:
            parts.append(f"{weight}  ×  {reps}")
        elif weight:
            parts.append(weight)
        elif reps:
            parts.append(reps)

    if row.duration_seconds is not None:
        mins, secs = divmod(row.duration_seconds, 60)
        parts.append(_mark(f"{mins}:{secs:02d}", "duration_seconds", row.uncertain_fields))
    if row.distance_meters is not None:
        parts.append(_mark(f"{row.distance_meters:g} m", "distance_meters", row.uncertain_fields))
    if row.heart_rate_bpm is not None:
        parts.append(_mark(f"HR {row.heart_rate_bpm}", "heart_rate_bpm", row.uncertain_fields))
    if row.rpe is not None:
        parts.append(_mark(f"RPE {row.rpe:g}", "rpe", row.uncertain_fields))
    if row.quality:
        parts.append(_mark(row.quality, "quality", row.uncertain_fields))
    if row.failure_technique:
        parts.append(f"[dim]│ {row.failure_technique}[/dim]")
    if row.notes:
        parts.append(f"[dim]{row.notes}[/dim]")

    return "   ".join(parts)


class TerminalRenderer:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def render(self, card: ConfirmationCard) -> None:
        self._render_session_header(card.session_header)
        for exercise_card in card.exercises:
            self.console.print()
            self._render_exercise_card(exercise_card)

    def _render_session_header(self, header: SessionHeader) -> None:
        self.console.rule(style="dim")
        parts = [_mark(header.date, "date", header.uncertain_fields)]
        if header.focus:
            parts.append(_mark(header.focus, "focus", header.uncertain_fields))
        if header.program:
            prog = header.program
            if header.phase is not None:
                prog += f" P{header.phase}"
            if header.week is not None:
                prog += f"W{header.week}"
            parts.append(_mark(prog, "program", header.uncertain_fields))
        if header.duration_minutes is not None:
            parts.append(
                _mark(f"{header.duration_minutes} min", "duration_minutes", header.uncertain_fields)
            )
        self.console.print("  " + "  |  ".join(parts), highlight=False)
        self.console.rule(style="dim")

    def _render_exercise_card(self, card: ExerciseCard) -> None:
        self._render_exercise_header(card.header)
        if card.warmup_rows:
            self._render_warmup_rows(card.warmup_rows)
        self._render_working_set_rows(card.working_set_rows)
        if card.warmup_note_preview:
            self._render_note("Warmup note", card.warmup_note_preview)
        if card.note_preview:
            self._render_note("Note", card.note_preview)

    def _render_exercise_header(self, header: ExerciseHeader) -> None:
        name = _mark(header.name, "name", header.uncertain_fields)
        self.console.print(f"  [bold]Exercise {header.number}:[/bold] {name}", highlight=False)
        if header.goal:
            goal_str = _fmt_goal(header.goal)
            if goal_str:
                self.console.print(f"    Goal: {goal_str}", highlight=False)

    def _render_warmup_rows(self, rows: list[WarmupRow]) -> None:
        self.console.print("    [dim]Warmup:[/dim]", highlight=False)
        for row in rows:
            weight = _mark(f"{row.weight_kg:g} kg", "weight_kg", row.uncertain_fields)
            reps = f"  × {row.rep_count}" if row.rep_count is not None else ""
            note = f"  ({row.notes})" if row.notes else ""
            self.console.print(f"      {row.number}.  {weight}{reps}{note}", highlight=False)

    def _render_working_set_rows(self, rows: list[WorkingSetRow]) -> None:
        self.console.print("    [dim]Sets:[/dim]", highlight=False)
        for row in rows:
            line = _fmt_working_set(row)
            self.console.print(f"      {row.number}.  {line}", highlight=False)

    def _render_note(self, label: str, preview: NotePreview) -> None:
        self.console.print(f"    [dim]{label}:[/dim] {preview.display}", highlight=False)
