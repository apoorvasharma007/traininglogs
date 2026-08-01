from __future__ import annotations

from pydantic import ValidationError

from traininglogs.agent.providers import ExtractionProvider
from traininglogs.agent.schemas import LLMParserError, TrainingLogLLMExtract


class LLMExtractValidator:
    def __init__(self, provider: ExtractionProvider) -> None:
        self._provider = provider

    def apply_correction(
        self, extract: TrainingLogLLMExtract, correction: str
    ) -> TrainingLogLLMExtract:
        current_json = extract.model_dump_json(indent=2)
        prompt = (
            f"Current extract:\n{current_json}\n\n"
            f"User correction:\n{correction}\n\n"
            "Apply the correction and return the complete updated extract using the "
            "extract_workout tool. Keep all unchanged fields exactly as they are."
        )
        tool_schema = TrainingLogLLMExtract.model_json_schema()
        raw = self._provider.extract(prompt, tool_schema)
        try:
            return TrainingLogLLMExtract.model_validate(raw)
        except ValidationError as exc:
            raise LLMParserError(
                f"Corrected extract failed validation:\n{exc}"
            ) from exc
