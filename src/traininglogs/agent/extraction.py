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
