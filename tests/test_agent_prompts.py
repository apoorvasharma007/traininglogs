"""Guard tests for the three focused prompts added by the orchestration refactor
(splitter/shell/worker). Prose content, not logic — these exist to catch the kind of
silent structural regression a prompt edit could introduce (e.g. the worker prompt
losing the movement-skill conventions it's supposed to reuse)."""
from __future__ import annotations

from traininglogs.agent.prompts import (
    MOVEMENT_SKILL_CONVENTIONS,
    SHELL_SYSTEM_PROMPT,
    SPLITTER_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    WORKER_SYSTEM_PROMPT,
)


class TestSystemPromptUnchanged:
    def test_system_prompt_still_ends_with_movement_skill_conventions(self) -> None:
        assert SYSTEM_PROMPT.endswith(MOVEMENT_SKILL_CONVENTIONS)


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
    def test_targets_by_position_not_name(self) -> None:
        assert "not by name (names can repeat)" in WORKER_SYSTEM_PROMPT

    def test_reuses_movement_skill_conventions_verbatim(self) -> None:
        assert WORKER_SYSTEM_PROMPT.endswith(MOVEMENT_SKILL_CONVENTIONS)

    def test_has_no_session_level_fields(self) -> None:
        for field in ("session_duration_minutes", "is_deload_week", "\"program\":"):
            assert field not in WORKER_SYSTEM_PROMPT

    def test_uncertain_fields_are_relative_to_the_exercise(self) -> None:
        assert "relative to this exercise" in WORKER_SYSTEM_PROMPT
