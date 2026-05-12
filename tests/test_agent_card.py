import pytest

from traininglogs.agent.validation_card_data import (
    UserValidationCard,
    ExerciseCard,
    ExerciseHeader,
    GoalSummary,
    NotePreview,
    NOTE_PREVIEW_CHARS,
    SessionHeader,
    WarmupRow,
    WorkingSetRow,
)


# --- NotePreview ---

class TestNotePreview:
    def test_short_text_no_truncation(self) -> None:
        np = NotePreview("short note")
        assert np.display == "short note"

    def test_exact_boundary_no_truncation(self) -> None:
        text = "x" * NOTE_PREVIEW_CHARS
        np = NotePreview(text)
        assert np.display == text
        assert "..." not in np.display

    def test_long_text_truncated_with_ellipsis(self) -> None:
        text = "a" * (NOTE_PREVIEW_CHARS + 10)
        np = NotePreview(text)
        assert np.display.endswith("...")
        assert len(np.display) <= NOTE_PREVIEW_CHARS + 3

    def test_trailing_whitespace_stripped_before_ellipsis(self) -> None:
        text = "word   " + "x" * NOTE_PREVIEW_CHARS
        np = NotePreview(text)
        assert not np.display[:-3].endswith(" ")

    def test_custom_max_chars(self) -> None:
        np = NotePreview("hello world", max_chars=5)
        assert np.display == "hello..."

    def test_empty_string(self) -> None:
        np = NotePreview("")
        assert np.display == ""

    def test_full_text_preserved(self) -> None:
        text = "full text stored"
        np = NotePreview(text)
        assert np.full_text == text


# --- GoalSummary ---

class TestGoalSummary:
    def test_all_none_by_default(self) -> None:
        g = GoalSummary()
        assert g.weight_kg is None
        assert g.sets is None
        assert g.rep_range_min is None
        assert g.rep_range_max is None
        assert g.rest_minutes is None
        assert g.rest_seconds is None
        assert g.distance_meters is None
        assert g.target_duration_seconds is None

    def test_strength_goal(self) -> None:
        g = GoalSummary(weight_kg=63.0, sets=3, rep_range_min=10, rep_range_max=12, rest_minutes=2)
        assert g.weight_kg == 63.0
        assert g.sets == 3
        assert g.rep_range_min == 10
        assert g.rep_range_max == 12
        assert g.rest_minutes == 2

    def test_activity_goal(self) -> None:
        g = GoalSummary(distance_meters=5000.0, target_duration_seconds=1800)
        assert g.distance_meters == 5000.0
        assert g.target_duration_seconds == 1800


# --- SessionHeader ---

class TestSessionHeader:
    def test_minimal_construction(self) -> None:
        h = SessionHeader(date="2026-05-12")
        assert h.date == "2026-05-12"
        assert h.program is None
        assert h.phase is None
        assert h.week is None
        assert h.focus is None
        assert h.duration_minutes is None
        assert h.uncertain_fields == frozenset()

    def test_full_construction(self) -> None:
        h = SessionHeader(
            date="2026-05-12",
            program="Hypertrophy Block",
            phase=3,
            week=2,
            focus="Lower Strength",
            duration_minutes=90,
            uncertain_fields=frozenset({"duration_minutes"}),
        )
        assert h.program == "Hypertrophy Block"
        assert h.duration_minutes == 90
        assert "duration_minutes" in h.uncertain_fields

    def test_uncertain_fields_immutable(self) -> None:
        h = SessionHeader(date="2026-01-01", uncertain_fields=frozenset({"date"}))
        assert isinstance(h.uncertain_fields, frozenset)


# --- WarmupRow ---

class TestWarmupRow:
    def test_basic(self) -> None:
        row = WarmupRow(number=1, weight_kg=20.0)
        assert row.number == 1
        assert row.weight_kg == 20.0
        assert row.rep_count is None
        assert row.notes is None
        assert row.uncertain_fields == frozenset()

    def test_with_feel_note(self) -> None:
        row = WarmupRow(number=2, weight_kg=30.0, notes="feel")
        assert row.notes == "feel"

    def test_uncertain_field_flagged(self) -> None:
        row = WarmupRow(number=1, weight_kg=40.0, uncertain_fields=frozenset({"weight_kg"}))
        assert "weight_kg" in row.uncertain_fields


# --- WorkingSetRow ---

class TestWorkingSetRow:
    def test_strength_set(self) -> None:
        row = WorkingSetRow(
            number=1,
            weight_kg=63.0,
            reps="12",
            rpe=10.0,
            quality="good",
        )
        assert row.weight_kg == 63.0
        assert row.reps == "12"
        assert row.rpe == 10.0
        assert row.quality == "good"
        assert row.failure_technique is None
        assert row.uncertain_fields == frozenset()

    def test_partial_reps_formatted(self) -> None:
        row = WorkingSetRow(number=1, weight_kg=25.0, reps="8+1")
        assert row.reps == "8+1"

    def test_unilateral_reps_formatted(self) -> None:
        row = WorkingSetRow(number=1, weight_kg=0.0, reps="8L / 8R")
        assert row.reps == "8L / 8R"

    def test_failure_technique(self) -> None:
        row = WorkingSetRow(
            number=3,
            weight_kg=63.0,
            reps="11",
            rpe=10.0,
            failure_technique="LLP: 10 partial reps",
        )
        assert row.failure_technique == "LLP: 10 partial reps"

    def test_activity_set(self) -> None:
        row = WorkingSetRow(
            number=1,
            duration_seconds=1800,
            distance_meters=5000.0,
            heart_rate_bpm=155,
        )
        assert row.duration_seconds == 1800
        assert row.distance_meters == 5000.0
        assert row.heart_rate_bpm == 155
        assert row.weight_kg is None

    def test_uncertain_rpe(self) -> None:
        row = WorkingSetRow(number=1, weight_kg=100.0, rpe=9.0, uncertain_fields=frozenset({"rpe"}))
        assert "rpe" in row.uncertain_fields

    def test_multiple_uncertain_fields(self) -> None:
        row = WorkingSetRow(number=1, uncertain_fields=frozenset({"weight_kg", "rpe"}))
        assert "weight_kg" in row.uncertain_fields
        assert "rpe" in row.uncertain_fields


# --- ExerciseHeader ---

class TestExerciseHeader:
    def test_no_goal(self) -> None:
        h = ExerciseHeader(number=1, name="Squat")
        assert h.number == 1
        assert h.name == "Squat"
        assert h.goal is None
        assert h.uncertain_fields == frozenset()

    def test_with_goal(self) -> None:
        goal = GoalSummary(weight_kg=100.0, sets=3, rep_range_min=5, rep_range_max=8)
        h = ExerciseHeader(number=2, name="Deadlift", goal=goal)
        assert h.goal.weight_kg == 100.0

    def test_uncertain_name(self) -> None:
        h = ExerciseHeader(number=1, name="Leg Press?", uncertain_fields=frozenset({"name"}))
        assert "name" in h.uncertain_fields


# --- ExerciseCard ---

class TestExerciseCard:
    def test_minimal(self) -> None:
        header = ExerciseHeader(number=1, name="Plank")
        card = ExerciseCard(header=header)
        assert card.header.name == "Plank"
        assert card.warmup_rows == []
        assert card.working_set_rows == []
        assert card.note_preview is None
        assert card.warmup_note_preview is None

    def test_with_warmup_and_working_sets(self) -> None:
        header = ExerciseHeader(number=1, name="Bench Press")
        warmup = [WarmupRow(number=1, weight_kg=60.0, notes="feel")]
        sets = [WorkingSetRow(number=1, weight_kg=100.0, reps="5", rpe=8.0)]
        card = ExerciseCard(header=header, warmup_rows=warmup, working_set_rows=sets)
        assert len(card.warmup_rows) == 1
        assert len(card.working_set_rows) == 1

    def test_note_preview_attached(self) -> None:
        header = ExerciseHeader(number=1, name="Cable Row")
        note = NotePreview("Keep elbows close throughout the movement range")
        card = ExerciseCard(header=header, note_preview=note)
        assert card.note_preview is not None
        assert "elbows" in card.note_preview.display


# --- UserValidationCard ---

class TestUserValidationCard:
    def test_empty_exercises(self) -> None:
        header = SessionHeader(date="2026-05-12")
        card = UserValidationCard(session_header=header)
        assert card.exercises == []

    def test_full_card(self) -> None:
        session_header = SessionHeader(
            date="2026-05-12",
            program="Test Program",
            phase=3,
            week=11,
            focus="Lower Strength",
            duration_minutes=150,
        )
        ex_header = ExerciseHeader(
            number=1,
            name="Seated Leg Hamstring Curl",
            goal=GoalSummary(weight_kg=63.0, sets=3, rep_range_min=10, rep_range_max=12),
        )
        warmup_rows = [
            WarmupRow(number=1, weight_kg=29.0, notes="feel"),
            WarmupRow(number=2, weight_kg=57.0, notes="feel"),
        ]
        working_set_rows = [
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
        ]
        exercise_card = ExerciseCard(
            header=ex_header,
            warmup_rows=warmup_rows,
            working_set_rows=working_set_rows,
        )
        card = UserValidationCard(session_header=session_header, exercises=[exercise_card])

        assert card.session_header.date == "2026-05-12"
        assert card.session_header.focus == "Lower Strength"
        assert len(card.exercises) == 1
        assert card.exercises[0].header.name == "Seated Leg Hamstring Curl"
        assert len(card.exercises[0].warmup_rows) == 2
        assert len(card.exercises[0].working_set_rows) == 3
        assert card.exercises[0].working_set_rows[2].failure_technique == "LLP: 10 partial reps"
