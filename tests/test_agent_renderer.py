import io

import pytest
from rich.console import Console

from traininglogs.agent.validation_card_data import (
    UserValidationCard,
    ExerciseCard,
    ExerciseHeader,
    GoalSummary,
    NotePreview,
    SessionHeader,
    WarmupRow,
    WorkingSetRow,
)
from traininglogs.agent.renderer import TerminalRenderer, _fmt_goal, _fmt_working_set, _mark


def _capture(card: UserValidationCard) -> str:
    buf = io.StringIO()
    console = Console(file=buf, no_color=True, highlight=False, width=120)
    renderer = TerminalRenderer(console=console)
    renderer.render(card)
    return buf.getvalue()


def _minimal_card(
    date: str = "2026-05-12",
    exercises: list[ExerciseCard] | None = None,
) -> UserValidationCard:
    return UserValidationCard(
        session_header=SessionHeader(date=date),
        exercises=exercises or [],
    )


# --- _mark ---

class TestMark:
    def test_certain_field_unchanged(self) -> None:
        assert _mark("10.0", "rpe", frozenset()) == "10.0"

    def test_uncertain_field_wrapped(self) -> None:
        result = _mark("10.0", "rpe", frozenset({"rpe"}))
        assert "10.0?" in result
        assert "yellow" in result

    def test_only_named_field_marked(self) -> None:
        result = _mark("good", "quality", frozenset({"rpe"}))
        assert result == "good"


# --- _fmt_goal ---

class TestFmtGoal:
    def test_strength_goal_full(self) -> None:
        g = GoalSummary(weight_kg=63.0, sets=3, rep_range_min=10, rep_range_max=12, rest_minutes=2)
        out = _fmt_goal(g)
        assert "63 kg" in out
        assert "3 sets" in out
        assert "10" in out
        assert "12 reps" in out
        assert "2 min rest" in out

    def test_empty_goal_produces_empty_string(self) -> None:
        assert _fmt_goal(GoalSummary()) == ""

    def test_activity_goal(self) -> None:
        g = GoalSummary(distance_meters=5000.0, target_duration_seconds=1830)
        out = _fmt_goal(g)
        assert "5000 m" in out
        assert "30:30" in out

    def test_single_sided_rep_range(self) -> None:
        g = GoalSummary(rep_range_min=8)
        assert "8+ reps" in _fmt_goal(g)

    def test_rest_seconds(self) -> None:
        g = GoalSummary(rest_seconds=90)
        assert "90s rest" in _fmt_goal(g)


# --- _fmt_working_set ---

class TestFmtWorkingSet:
    def test_basic_strength(self) -> None:
        row = WorkingSetRow(number=1, weight_kg=63.0, reps="12", rpe=10.0, quality="good")
        out = _fmt_working_set(row)
        assert "63 kg" in out
        assert "12" in out
        assert "RPE 10" in out
        assert "good" in out

    def test_partial_reps(self) -> None:
        row = WorkingSetRow(number=1, weight_kg=63.0, reps="11+2")
        out = _fmt_working_set(row)
        assert "11+2" in out

    def test_failure_technique(self) -> None:
        row = WorkingSetRow(
            number=1,
            weight_kg=63.0,
            reps="11",
            rpe=10.0,
            failure_technique="LLP: 10 partial reps",
        )
        out = _fmt_working_set(row)
        assert "LLP: 10 partial reps" in out

    def test_activity_set(self) -> None:
        row = WorkingSetRow(number=1, duration_seconds=1800, distance_meters=5000.0, heart_rate_bpm=155)
        out = _fmt_working_set(row)
        assert "30:00" in out
        assert "5000 m" in out
        assert "HR 155" in out

    def test_uncertain_rpe_marked(self) -> None:
        row = WorkingSetRow(number=1, weight_kg=100.0, rpe=8.0, uncertain_fields=frozenset({"rpe"}))
        out = _fmt_working_set(row)
        assert "RPE 8?" in out

    def test_certain_weight_not_marked(self) -> None:
        row = WorkingSetRow(number=1, weight_kg=100.0, uncertain_fields=frozenset({"rpe"}))
        out = _fmt_working_set(row)
        assert "100 kg?" not in out
        assert "100 kg" in out


# --- TerminalRenderer.render ---

class TestTerminalRendererSessionHeader:
    def test_date_present(self) -> None:
        card = _minimal_card(date="2026-05-12")
        out = _capture(card)
        assert "2026-05-12" in out

    def test_focus_present(self) -> None:
        card = UserValidationCard(
            session_header=SessionHeader(date="2026-05-12", focus="Lower Strength"),
        )
        out = _capture(card)
        assert "Lower Strength" in out

    def test_program_phase_week_formatted(self) -> None:
        card = UserValidationCard(
            session_header=SessionHeader(
                date="2026-05-12",
                program="Test Program",
                phase=3,
                week=11,
            ),
        )
        out = _capture(card)
        assert "Test Program P3W11" in out

    def test_duration_present(self) -> None:
        card = UserValidationCard(
            session_header=SessionHeader(date="2026-05-12", duration_minutes=90),
        )
        out = _capture(card)
        assert "90 min" in out

    def test_uncertain_date_marked(self) -> None:
        card = UserValidationCard(
            session_header=SessionHeader(
                date="2026-05-12",
                uncertain_fields=frozenset({"date"}),
            ),
        )
        out = _capture(card)
        assert "2026-05-12?" in out

    def test_rule_dividers_present(self) -> None:
        out = _capture(_minimal_card())
        assert "─" in out or "—" in out or "-" in out


class TestTerminalRendererExercise:
    def _card_with_exercise(self, **kwargs) -> UserValidationCard:
        header = ExerciseHeader(number=1, name="Squat", **kwargs)
        return UserValidationCard(
            session_header=SessionHeader(date="2026-05-12"),
            exercises=[ExerciseCard(header=header)],
        )

    def test_exercise_name_present(self) -> None:
        out = _capture(self._card_with_exercise())
        assert "Squat" in out

    def test_exercise_number_present(self) -> None:
        out = _capture(self._card_with_exercise())
        assert "Exercise 1" in out

    def test_uncertain_name_marked(self) -> None:
        card = self._card_with_exercise(uncertain_fields=frozenset({"name"}))
        out = _capture(card)
        assert "Squat?" in out

    def test_goal_rendered_when_present(self) -> None:
        card = self._card_with_exercise(
            goal=GoalSummary(weight_kg=100.0, sets=3, rep_range_min=5, rep_range_max=8)
        )
        out = _capture(card)
        assert "Goal:" in out
        assert "100 kg" in out
        assert "3 sets" in out

    def test_no_goal_line_when_absent(self) -> None:
        out = _capture(self._card_with_exercise())
        assert "Goal:" not in out


class TestTerminalRendererWarmup:
    def test_warmup_section_label(self) -> None:
        card = UserValidationCard(
            session_header=SessionHeader(date="2026-05-12"),
            exercises=[
                ExerciseCard(
                    header=ExerciseHeader(number=1, name="Bench"),
                    warmup_rows=[WarmupRow(number=1, weight_kg=60.0, notes="feel")],
                )
            ],
        )
        out = _capture(card)
        assert "Warmup:" in out
        assert "60 kg" in out
        assert "feel" in out

    def test_no_warmup_section_when_empty(self) -> None:
        card = UserValidationCard(
            session_header=SessionHeader(date="2026-05-12"),
            exercises=[ExerciseCard(header=ExerciseHeader(number=1, name="Bench"))],
        )
        out = _capture(card)
        assert "Warmup:" not in out

    def test_warmup_rep_count_shown(self) -> None:
        card = UserValidationCard(
            session_header=SessionHeader(date="2026-05-12"),
            exercises=[
                ExerciseCard(
                    header=ExerciseHeader(number=1, name="Bench"),
                    warmup_rows=[WarmupRow(number=1, weight_kg=40.0, rep_count=10)],
                )
            ],
        )
        out = _capture(card)
        assert "× 10" in out

    def test_uncertain_warmup_weight_marked(self) -> None:
        card = UserValidationCard(
            session_header=SessionHeader(date="2026-05-12"),
            exercises=[
                ExerciseCard(
                    header=ExerciseHeader(number=1, name="Bench"),
                    warmup_rows=[
                        WarmupRow(number=1, weight_kg=60.0, uncertain_fields=frozenset({"weight_kg"}))
                    ],
                )
            ],
        )
        out = _capture(card)
        assert "60 kg?" in out


class TestTerminalRendererWorkingSets:
    def _card_with_sets(self, rows: list[WorkingSetRow]) -> UserValidationCard:
        return UserValidationCard(
            session_header=SessionHeader(date="2026-05-12"),
            exercises=[
                ExerciseCard(
                    header=ExerciseHeader(number=1, name="Deadlift"),
                    working_set_rows=rows,
                )
            ],
        )

    def test_sets_section_label(self) -> None:
        out = _capture(self._card_with_sets([WorkingSetRow(number=1, weight_kg=140.0, reps="5")]))
        assert "Sets:" in out

    def test_weight_and_reps_present(self) -> None:
        out = _capture(self._card_with_sets([WorkingSetRow(number=1, weight_kg=140.0, reps="5")]))
        assert "140 kg" in out
        assert "5" in out

    def test_rpe_present(self) -> None:
        out = _capture(self._card_with_sets([WorkingSetRow(number=1, weight_kg=140.0, reps="5", rpe=8.5)]))
        assert "RPE 8.5" in out

    def test_quality_present(self) -> None:
        out = _capture(self._card_with_sets([WorkingSetRow(number=1, weight_kg=100.0, reps="8", quality="perfect")]))
        assert "perfect" in out

    def test_failure_technique_present(self) -> None:
        out = _capture(
            self._card_with_sets([
                WorkingSetRow(number=1, weight_kg=63.0, reps="11", rpe=10.0, failure_technique="LLP: 10 partial reps")
            ])
        )
        assert "LLP: 10 partial reps" in out

    def test_uncertain_rpe_marked(self) -> None:
        out = _capture(
            self._card_with_sets([
                WorkingSetRow(number=1, weight_kg=100.0, rpe=9.0, uncertain_fields=frozenset({"rpe"}))
            ])
        )
        assert "RPE 9?" in out

    def test_multiple_sets_all_rendered(self) -> None:
        rows = [
            WorkingSetRow(number=1, weight_kg=100.0, reps="5", rpe=8.0),
            WorkingSetRow(number=2, weight_kg=100.0, reps="5", rpe=9.0),
            WorkingSetRow(number=3, weight_kg=100.0, reps="4", rpe=10.0),
        ]
        out = _capture(self._card_with_sets(rows))
        assert "1." in out
        assert "2." in out
        assert "3." in out


class TestTerminalRendererNotes:
    def test_note_preview_shown(self) -> None:
        card = UserValidationCard(
            session_header=SessionHeader(date="2026-05-12"),
            exercises=[
                ExerciseCard(
                    header=ExerciseHeader(number=1, name="Cable Row"),
                    note_preview=NotePreview("Keep elbows close throughout the movement"),
                )
            ],
        )
        out = _capture(card)
        assert "Note:" in out
        assert "Keep elbows close" in out

    def test_warmup_note_preview_shown(self) -> None:
        card = UserValidationCard(
            session_header=SessionHeader(date="2026-05-12"),
            exercises=[
                ExerciseCard(
                    header=ExerciseHeader(number=1, name="Squat"),
                    warmup_note_preview=NotePreview("Pyramid warmup"),
                )
            ],
        )
        out = _capture(card)
        assert "Warmup note:" in out
        assert "Pyramid warmup" in out

    def test_truncated_note_shown_with_ellipsis(self) -> None:
        long_note = "a" * 100
        card = UserValidationCard(
            session_header=SessionHeader(date="2026-05-12"),
            exercises=[
                ExerciseCard(
                    header=ExerciseHeader(number=1, name="Press"),
                    note_preview=NotePreview(long_note),
                )
            ],
        )
        out = _capture(card)
        assert "..." in out


class TestTerminalRendererFullCard:
    def test_full_strength_session(self) -> None:
        card = UserValidationCard(
            session_header=SessionHeader(
                date="2026-05-12",
                program="Test Program",
                phase=3,
                week=11,
                focus="Lower Strength",
                duration_minutes=150,
            ),
            exercises=[
                ExerciseCard(
                    header=ExerciseHeader(
                        number=1,
                        name="Seated Leg Hamstring Curl",
                        goal=GoalSummary(weight_kg=63.0, sets=3, rep_range_min=10, rep_range_max=12),
                    ),
                    warmup_rows=[
                        WarmupRow(number=1, weight_kg=29.0, notes="feel"),
                        WarmupRow(number=2, weight_kg=57.0, notes="feel"),
                    ],
                    working_set_rows=[
                        WorkingSetRow(number=1, weight_kg=63.0, reps="12", rpe=10.0, quality="good"),
                        WorkingSetRow(number=2, weight_kg=63.0, reps="12", rpe=10.0, quality="good"),
                        WorkingSetRow(
                            number=3,
                            weight_kg=63.0,
                            reps="11",
                            rpe=10.0,
                            quality="good",
                            failure_technique="LLP: 10 partial reps",
                        ),
                    ],
                ),
                ExerciseCard(
                    header=ExerciseHeader(
                        number=2,
                        name="Smith Machine Static Lunge",
                        goal=GoalSummary(weight_kg=40.0, sets=3, rep_range_min=6, rep_range_max=8),
                    ),
                    working_set_rows=[
                        WorkingSetRow(number=1, weight_kg=40.0, reps="8", rpe=8.5, quality="good"),
                    ],
                ),
            ],
        )
        out = _capture(card)

        assert "2026-05-12" in out
        assert "Lower Strength" in out
        assert "Test Program P3W11" in out
        assert "150 min" in out
        assert "Exercise 1" in out
        assert "Seated Leg Hamstring Curl" in out
        assert "63 kg" in out
        assert "LLP: 10 partial reps" in out
        assert "Exercise 2" in out
        assert "Smith Machine Static Lunge" in out
        assert "RPE 8.5" in out
