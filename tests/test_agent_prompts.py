"""Guard tests for the three prompts that are actually sent (splitter/shell/worker).

Prose content, not logic — these catch the kind of silent structural regression a prompt edit
introduces. The monolithic SYSTEM_PROMPT was deleted on 2026-08-09 with the parser it belonged
to; the conventions it carried that the live prompts do not are recorded in
docs/extraction-conventions.md."""
from __future__ import annotations

from traininglogs.agent.prompts import (
    SHELL_SYSTEM_PROMPT,
    SPLITTER_SYSTEM_PROMPT,
    WORKER_SYSTEM_PROMPT,
)


class TestSplitterPrompt:
    def test_excludes_warmup_and_cooldown(self) -> None:
        assert "Do NOT include warmup or cooldown movements" in SPLITTER_SYSTEM_PROMPT

    def test_supersets_are_separate_exercises(self) -> None:
        assert "A superset or circuit is two or more separate exercises" in SPLITTER_SYSTEM_PROMPT

    def test_does_not_ask_for_set_detail(self) -> None:
        assert "Do not extract sets, reps, weights" in SPLITTER_SYSTEM_PROMPT


class TestShellPrompt:
    def test_defers_exercises_to_a_separate_call(self) -> None:
        assert "extracted separately" in SHELL_SYSTEM_PROMPT

    def test_has_no_exercise_level_fields(self) -> None:
        for field in ("rpe", "weight_kg", "rep_count", "modality", "tags"):
            assert field not in SHELL_SYSTEM_PROMPT

    def test_carries_program_phase_week_convention(self) -> None:
        assert "leave program, phase, and week all unset" in SHELL_SYSTEM_PROMPT


class TestWorkerPrompt:
    """Rewritten 2026-08-06 for the lean extraction schema. Field scope now lives in
    Field(description=...) on the schema rather than as rules here, so these guard the things
    the prompt is still uniquely responsible for: which exercise to extract, copying rather
    than interpreting, and the examples."""

    def test_targets_by_position(self) -> None:
        assert "position" in WORKER_SYSTEM_PROMPT
        assert "extract only the one at your position" in WORKER_SYSTEM_PROMPT

    def test_asks_for_a_source_line_on_every_set(self) -> None:
        assert "source_line" in WORKER_SYSTEM_PROMPT
        assert "character for character" in WORKER_SYSTEM_PROMPT

    def test_tells_the_model_to_copy_rather_than_interpret(self) -> None:
        assert "Do not tidy it, convert it, renumber it, or interpret it" in WORKER_SYSTEM_PROMPT

    def test_carries_worked_examples(self) -> None:
        """Examples replaced ~2,200 characters of movement-skill conventions. Research puts
        1-4 real examples ahead of long rule lists; if these go, that trade is silently undone."""
        assert WORKER_SYSTEM_PROMPT.count("Output:") >= 3
        assert "Ring Support Hold" in WORKER_SYSTEM_PROMPT      # timed sets, no weight
        assert "Wrist Flexion DB Curl" in WORKER_SYSTEM_PROMPT  # per-side commentary

    def test_teaches_that_side_commentary_is_not_a_per_side_count(self) -> None:
        """The Wrist Flexion defect. The schema removed the field-choice; the example makes the
        right answer explicit."""
        assert "a remark about one side is a note, not a per-side rep count" in WORKER_SYSTEM_PROMPT

    def test_carries_the_warmup_notes_convention(self) -> None:
        assert "Warmup Notes" in WORKER_SYSTEM_PROMPT
        assert "is a warmup set" in WORKER_SYSTEM_PROMPT

    def test_has_no_session_level_fields(self) -> None:
        for field in ("session_duration_minutes", "is_deload_week", "Program:", "phase", "week"):
            assert field not in WORKER_SYSTEM_PROMPT, f"worker prompt mentions {field!r}"

    def test_does_not_ask_for_fields_the_schema_dropped(self) -> None:
        for field in ("tags", "modality", "movement_pattern", "target_muscle_groups",
                      "rep_tempo", "current_goal", "form_cues", "rep_count"):
            assert field not in WORKER_SYSTEM_PROMPT, f"worker prompt mentions {field!r}"


class TestFieldScopeLivesInTheSchema:
    """Better field descriptions accounted for 34% of measured accuracy improvements in
    production extraction work, so scope belongs on the schema rather than in prose."""

    def test_every_extraction_field_is_described(self) -> None:
        from traininglogs.agent.schemas import ExerciseExtract, SetExtract

        for model in (ExerciseExtract, SetExtract):
            for name, field in model.model_fields.items():
                assert field.description, f"{model.__name__}.{name} has no description"

    def test_the_copy_dont_convert_rule_is_on_the_reps_field(self) -> None:
        from traininglogs.agent.schemas import SetExtract

        description = SetExtract.model_fields["reps"].description or ""
        assert "exactly as written" in description
        assert "Do not convert it to a number" in description
