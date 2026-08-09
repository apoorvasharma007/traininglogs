from __future__ import annotations

from pydantic import ValidationError

from traininglogs.agent.patch import ExtractPatch, FieldEdit, PatchError, apply_edits
from traininglogs.agent.prompts import CORRECTION_SYSTEM_PROMPT
from traininglogs.agent.providers import ExtractionProvider
from traininglogs.agent.schemas import LLMParserError, TrainingLogLLMExtract

CORRECTION_TOOL_NAME = "edit_extraction"
CORRECTION_TOOL_DESCRIPTION = (
    "List the fields to change in the extraction, each as a path and its new value."
)


class LLMExtractValidator:
    def __init__(self, provider: ExtractionProvider) -> None:
        self._provider = provider

    def apply_correction(
        self, extract: TrainingLogLLMExtract, correction: str
    ) -> tuple[TrainingLogLLMExtract, list[FieldEdit]]:
        """Apply one person's correction, and report exactly what it changed.

        The model returns edits rather than a rewritten extract. Two things follow from that,
        neither of which the previous whole-document approach could promise:

        Fields the correction does not name cannot change, because Python copies the original
        and sets only the named paths. Previously the guarantee was the sentence "keep all
        unchanged fields exactly as they are" in a prompt, and nothing would have noticed a
        quietly altered set.

        And the reply is a few edits instead of a whole document, so a long session is no longer
        at risk of being truncated into a shorter one by the output ceiling -- which is what
        happened to 2 of 6 files in the evaluation, on this same path.
        """
        current_json = extract.model_dump_json(indent=2)
        prompt = (
            f"Current extraction:\n{current_json}\n\n"
            f"The person says:\n{correction}\n\n"
            "List the fields to change."
        )
        raw = self._provider.extract(
            prompt,
            ExtractPatch.model_json_schema(),
            CORRECTION_SYSTEM_PROMPT,
            CORRECTION_TOOL_NAME,
            CORRECTION_TOOL_DESCRIPTION,
            validate=ExtractPatch.model_validate,
        )

        try:
            patch = ExtractPatch.model_validate(raw)
        except ValidationError as exc:
            raise LLMParserError(f"Correction was not a usable patch:\n{exc}") from exc

        try:
            patched = apply_edits(extract.model_dump(mode="json"), patch.edits)
        except PatchError as exc:
            raise LLMParserError(f"Correction could not be applied: {exc}") from exc

        try:
            return TrainingLogLLMExtract.model_validate(patched), patch.edits
        except ValidationError as exc:
            raise LLMParserError(f"Corrected extract failed validation:\n{exc}") from exc
