from __future__ import annotations

from pydantic import ValidationError

from traininglogs.agent.providers import AnthropicProvider, ExtractionProvider
from traininglogs.agent.schemas import LLMParserError, TrainingLogLLMExtract


def parse(text: str, provider: ExtractionProvider | None = None) -> TrainingLogLLMExtract:
    provider = provider or AnthropicProvider()
    tool_schema = TrainingLogLLMExtract.model_json_schema()

    raw = provider.extract(text, tool_schema)

    try:
        return TrainingLogLLMExtract.model_validate(raw)
    except ValidationError as exc:
        raise LLMParserError(
            f"Extracted data did not pass validation:\n{exc}"
        ) from exc
