from __future__ import annotations

from pydantic import ValidationError

from traininglogs.agent.prompts import (
    SHELL_SYSTEM_PROMPT,
    SPLITTER_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    WORKER_SYSTEM_PROMPT,
)
from traininglogs.agent.providers import AnthropicProvider, ExtractionProvider
from traininglogs.agent.schemas import (
    ExerciseExtract,
    ExerciseSplit,
    LLMParserError,
    SessionShellExtract,
    TrainingLogLLMExtract,
)
from traininglogs.models.models import Exercise

TOOL_NAME = "extract_workout"
TOOL_DESCRIPTION = "Extract structured workout data from the session text."

SEGMENT_TOOL_NAME = "split_exercises"
SEGMENT_TOOL_DESCRIPTION = (
    "List the main working exercises in the session text, in order, with their positions."
)

SHELL_TOOL_NAME = "extract_session_shell"
SHELL_TOOL_DESCRIPTION = (
    "Extract the session-level data — everything except the individual exercises."
)

WORKER_TOOL_NAME = "extract_exercise"
WORKER_TOOL_DESCRIPTION = "Extract the exercise at the given position from the session text."


def parse(text: str, provider: ExtractionProvider | None = None) -> TrainingLogLLMExtract:
    provider = provider or AnthropicProvider()
    tool_schema = TrainingLogLLMExtract.model_json_schema()

    raw = provider.extract(text, tool_schema, SYSTEM_PROMPT, TOOL_NAME, TOOL_DESCRIPTION)

    try:
        return TrainingLogLLMExtract.model_validate(raw)
    except ValidationError as exc:
        raise LLMParserError(
            f"Extracted data did not pass validation:\n{exc}"
        ) from exc


def segment(text: str, provider: ExtractionProvider | None = None) -> ExerciseSplit:
    """List the main working exercises in `text`, in order, as {position, name} pairs."""
    provider = provider or AnthropicProvider()
    tool_schema = ExerciseSplit.model_json_schema()

    raw = provider.extract(
        text, tool_schema, SPLITTER_SYSTEM_PROMPT, SEGMENT_TOOL_NAME, SEGMENT_TOOL_DESCRIPTION
    )

    try:
        return ExerciseSplit.model_validate(raw)
    except ValidationError as exc:
        raise LLMParserError(f"Exercise split did not pass validation:\n{exc}") from exc


def extract_shell(text: str, provider: ExtractionProvider | None = None) -> SessionShellExtract:
    """Extract everything about `text` except the individual exercises."""
    provider = provider or AnthropicProvider()
    tool_schema = SessionShellExtract.model_json_schema()

    raw = provider.extract(
        text, tool_schema, SHELL_SYSTEM_PROMPT, SHELL_TOOL_NAME, SHELL_TOOL_DESCRIPTION
    )

    try:
        return SessionShellExtract.model_validate(raw)
    except ValidationError as exc:
        raise LLMParserError(f"Session shell did not pass validation:\n{exc}") from exc


def extract_exercise(
    text: str, position: int, provider: ExtractionProvider | None = None
) -> ExerciseExtract:
    """Extract only the exercise at `position` from the full session `text`. Self-contained:
    depends on nothing but its own inputs, so workers can run independently of each other."""
    provider = provider or AnthropicProvider()
    tool_schema = ExerciseExtract.model_json_schema()
    prompt = f"Extract exercise number {position}.\n\nSession text:\n{text}"

    raw = provider.extract(
        prompt, tool_schema, WORKER_SYSTEM_PROMPT, WORKER_TOOL_NAME, WORKER_TOOL_DESCRIPTION
    )

    try:
        return ExerciseExtract.model_validate(raw)
    except ValidationError as exc:
        raise LLMParserError(
            f"Exercise {position} extraction did not pass validation:\n{exc}"
        ) from exc


def _placeholder_exercise(position: int, name: str, error: str) -> Exercise:
    return Exercise(
        number=position,
        name=name,
        notes=f"Extraction failed for this exercise: {error}",
    )


def assemble(text: str, provider: ExtractionProvider | None = None) -> TrainingLogLLMExtract:
    """Run the splitter, the session shell, and one worker call per exercise (sequential),
    then glue the results into a TrainingLogLLMExtract. A worker that fails becomes a
    flagged placeholder exercise plus a warning — never a crash or a silent gap."""
    provider = provider or AnthropicProvider()

    split = segment(text, provider=provider)
    shell = extract_shell(text, provider=provider)

    exercises: list[Exercise] = []
    uncertain_fields: list[str] = list(shell.uncertain_fields)
    warnings: list[str] = []

    for i, entry in enumerate(split.exercises):
        try:
            worker_result = extract_exercise(text, entry.position, provider=provider)
        except LLMParserError as exc:
            exercises.append(_placeholder_exercise(entry.position, entry.name, str(exc)))
            warnings.append(
                f"Exercise {entry.position} ({entry.name}) failed to extract: {exc}"
            )
            continue

        exercises.append(worker_result.exercise)
        uncertain_fields.extend(
            f"exercises.{i}.{path}" for path in worker_result.uncertain_fields
        )

    return TrainingLogLLMExtract(
        date=shell.date,
        program=shell.program,
        phase=shell.phase,
        week=shell.week,
        is_deload_week=shell.is_deload_week,
        focus=shell.focus,
        session_duration_minutes=shell.session_duration_minutes,
        warmup=shell.warmup,
        exercises=exercises,
        cooldown=shell.cooldown,
        notes=shell.notes,
        uncertain_fields=uncertain_fields,
        warnings=warnings,
    )
