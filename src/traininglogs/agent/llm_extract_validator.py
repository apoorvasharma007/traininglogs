"""Validate and correct AI extractions via user fixes."""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from traininglogs.agent.patch import ExtractPatch, FieldEdit, PatchError, apply_edits
from traininglogs.agent.prompts import CORRECTION_SYSTEM_PROMPT
from traininglogs.agent.providers import ExtractionProvider
from traininglogs.agent.schemas import LLMParserError, TrainingLogLLMExtract

CORRECTION_TOOL_NAME = "edit_extraction"
CORRECTION_TOOL_DESCRIPTION = (
    "List the fields to change in the extraction, each as a path and its new value."
)


# What each field is called on the card, for the person reading why a fix was refused.
_FIELD_NAMES = {
    "weight_kg": "weight",
    "rep_count": "reps",
    "full": "reps",
    "rpe": "RPE",
    "session_duration_minutes": "duration",
}
_DIDNT_MATCH = (
    "Couldn't tell which part of the card to change. "
    'Name the exercise and the set, for example "Squat, set 2".'
)


class CorrectionRejected(LLMParserError):
    """The AI answered, but its fix can't be used. `plain` says why, for the person."""

    def __init__(self, message: str, plain: str) -> None:
        super().__init__(message)
        self.plain = plain


def _join(numbers: list[int]) -> str:
    text = [str(n) for n in numbers]
    return text[0] if len(text) == 1 else f"{', '.join(text[:-1])} and {text[-1]}"


def describe_problems(exc: ValidationError, data: dict[str, Any]) -> str:
    """One sentence per problem, naming the exercise and sets, e.g.
    "Bicep curl, warm-up sets 1 and 2: needs a weight." Sets with the same problem share one.
    """
    grouped: dict[tuple[str, str, str], list[int]] = {}
    for err in exc.errors():
        loc = list(err["loc"])
        where = ""
        if len(loc) >= 2 and loc[0] == "exercises" and isinstance(loc[1], int):
            try:
                where = data["exercises"][loc[1]].get("name") or ""
            except (IndexError, KeyError, AttributeError):
                where = ""
            where = where or f"Exercise {loc[1] + 1}"
            loc = loc[2:]
        kind, number = "", 0
        if len(loc) >= 2 and loc[0] in ("sets", "warmup_sets") and isinstance(loc[1], int):
            kind = "warm-up set" if loc[0] == "warmup_sets" else "set"
            number = loc[1] + 1
            loc = loc[2:]
        fields = [x for x in loc if isinstance(x, str)]
        field = fields[-1] if fields else ""
        label = _FIELD_NAMES.get(field, field.replace("_", " "))
        if err["type"] == "missing" or err.get("input") is None:
            problem = f"needs a {label}"
        elif err["type"].startswith(("float", "int")):
            problem = f"{label} must be a number, not {err['input']}"
        else:
            problem = f"{label} can't be {err['input']}"
        grouped.setdefault((where, kind, problem), []).append(number)

    lines = []
    for (where, kind, problem), numbers in grouped.items():
        sets = f"{kind}s {_join(numbers)}" if len(numbers) > 1 else f"{kind} {numbers[0]}"
        place = ", ".join(x for x in (where, sets if kind else "") if x)
        lines.append(f"{place}: {problem}." if place else f"{problem[0].upper()}{problem[1:]}.")
    return "\n".join(lines)


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
            raise CorrectionRejected(
                f"Correction was not a usable patch:\n{exc}", _DIDNT_MATCH
            ) from exc

        try:
            patched = apply_edits(extract.model_dump(mode="json"), patch.edits)
        except PatchError as exc:
            raise CorrectionRejected(
                f"Correction could not be applied: {exc}", _DIDNT_MATCH
            ) from exc

        try:
            return TrainingLogLLMExtract.model_validate(patched), patch.edits
        except ValidationError as exc:
            raise CorrectionRejected(
                f"Corrected extract failed validation:\n{exc}", describe_problems(exc, patched)
            ) from exc
