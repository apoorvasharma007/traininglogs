from __future__ import annotations

import re

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
    """Extract only the exercise at `position` from `text` — usually a pre-sliced, isolated
    excerpt for just this exercise (see _chunk_exercises), occasionally the full session as a
    fallback. Self-contained: depends on nothing but its own inputs, so workers can run
    independently of each other."""
    provider = provider or AnthropicProvider()
    tool_schema = ExerciseExtract.model_json_schema()
    prompt = (
        f"Extract exercise number {position}. If this excerpt contains only one exercise, "
        f"that is the one to extract. If it contains the full session instead, count the main "
        f"working exercise blocks (not warmup/cooldown) from the top to find position "
        f"{position}. Include its full Sets: section if it has one.\n\nText:\n{text}"
    )

    raw = provider.extract(
        prompt, tool_schema, WORKER_SYSTEM_PROMPT, WORKER_TOOL_NAME, WORKER_TOOL_DESCRIPTION
    )

    try:
        return ExerciseExtract.model_validate(raw)
    except ValidationError as exc:
        raise LLMParserError(
            f"Exercise {position} extraction did not pass validation:\n{exc}"
        ) from exc


# Sentinel prefix identifying a placeholder Exercise's notes field. Owned here and read by
# validation_card_builder.py to flag the exercise on the confirmation card — deliberately not
# a new field on the Exercise model itself, since that model's blast radius (DB, API) extends
# well beyond the AI-parser confirmation flow this refactor is scoped to.
PLACEHOLDER_NOTE_PREFIX = "Extraction failed for this exercise:"


def _placeholder_exercise(position: int, name: str, error: str) -> Exercise:
    return Exercise(
        number=position,
        name=name,
        notes=f"{PLACEHOLDER_NOTE_PREFIX} {error}",
    )


# A few extra lines past the next exercise's anchor, kept in each chunk as a safety margin in
# case a trailing remark runs slightly past where the next exercise's anchor line starts.
CHUNK_TRAILING_OVERLAP_LINES = 3


def _locate_anchor_lines(lines: list[str], split: ExerciseSplit) -> dict[int, int]:
    """Sequentially locate each exercise's anchor line number, searching forward from the line
    after the previous exercise's anchor. Sequential (not global) search is what makes this
    work even when the same anchor text appears more than once in the document (e.g. a
    repeated exercise name) — we're not asking "where does this occur anywhere," only "where
    does it occur next," using the ordering the splitter already gave us. A position whose
    anchor can't be found verbatim is simply omitted; the caller falls back to the full text
    for that one exercise rather than treating it as fatal."""
    located: dict[int, int] = {}
    search_from = 0
    for entry in split.exercises:
        anchor = entry.anchor.strip()
        if not anchor:
            continue
        for i in range(search_from, len(lines)):
            if anchor in lines[i]:
                located[entry.position] = i
                search_from = i + 1
                break
    return located


def _chunk_exercises(text: str, split: ExerciseSplit) -> dict[int, str]:
    """Slice `text` into one isolated chunk per successfully-located exercise: from its own
    anchor line to CHUNK_TRAILING_OVERLAP_LINES past the next located exercise's anchor line
    (or to the end of the document for the last one). Positions whose anchor couldn't be
    located are simply absent from the returned dict — assemble() falls back to the full text
    for those."""
    lines = text.split("\n")
    located = _locate_anchor_lines(lines, split)
    ordered_positions = sorted(located)

    chunks: dict[int, str] = {}
    for idx, position in enumerate(ordered_positions):
        start = located[position]
        if idx + 1 < len(ordered_positions):
            end = located[ordered_positions[idx + 1]] + CHUNK_TRAILING_OVERLAP_LINES
        else:
            end = len(lines)
        chunks[position] = "\n".join(lines[start : min(end, len(lines))])
    return chunks


_RPE_TOKEN_RE = re.compile(
    r"rpe\s*:?\s*(\d{1,2}(?:\.\d)?)(?:\s*-\s*(\d{1,2}(?:\.\d)?))?", re.IGNORECASE
)
_WEIGHT_KG_TOKEN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*kg\b", re.IGNORECASE)


def _rpe_tokens_in_text(text: str) -> set[float]:
    # A range ("RPE: 6-7") contributes only its upper bound — that's the value the extraction
    # convention (design session, 2026-07-26) says should land on the last set.
    return {
        float(high) if high else float(low)
        for low, high in _RPE_TOKEN_RE.findall(text)
    }


def _weight_kg_tokens_in_text(text: str) -> set[float]:
    # Intentionally kg-only, not lbs — an lbs value in the text is unit-converted before it
    # lands in weight_kg, so it would never textually match and would always false-positive.
    return {float(v) for v in _WEIGHT_KG_TOKEN_RE.findall(text)}


def _extracted_rpes(exercises: list[Exercise]) -> set[float]:
    return {s.rpe for ex in exercises for s in (ex.sets or []) if s.rpe is not None}


def _extracted_weights_kg(exercises: list[Exercise]) -> set[float]:
    from_sets = {s.weight_kg for ex in exercises for s in (ex.sets or []) if s.weight_kg is not None}
    from_warmup = {ws.weight_kg for ex in exercises for ws in (ex.warmup_sets or [])}
    return from_sets | from_warmup


def audit(text: str, split: ExerciseSplit, exercises: list[Exercise]) -> list[str]:
    """Deterministic, LLM-free check for the two failure shapes the split-call design exists
    to prevent: an exercise silently missing from the final list, or a value (RPE, weight)
    present in the raw text but absent from every field it could have landed in. Findings are
    a heuristic, not proof — a value can legitimately appear in text without being extractable
    data (e.g. an RPE mentioned in passing prose). Start narrow; grow the token patterns from
    real misses rather than guessing edge cases up front."""
    warnings: list[str] = []

    if len(exercises) != len(split.exercises):
        warnings.append(
            f"Exercise count mismatch: splitter found {len(split.exercises)} exercises, "
            f"but {len(exercises)} were assembled."
        )

    extracted_rpes = _extracted_rpes(exercises)
    for value in sorted(_rpe_tokens_in_text(text) - extracted_rpes):
        warnings.append(f"RPE {value} appears in the text but not in any extracted set.")

    extracted_weights = _extracted_weights_kg(exercises)
    for value in sorted(_weight_kg_tokens_in_text(text) - extracted_weights):
        warnings.append(f"Weight {value}kg appears in the text but not in any extracted set.")

    return warnings


def assemble(text: str, provider: ExtractionProvider | None = None) -> TrainingLogLLMExtract:
    """Run the splitter, the session shell, and one worker call per exercise (sequential),
    then glue the results into a TrainingLogLLMExtract. Each worker gets an isolated,
    pre-sliced chunk of `text` for just its own exercise when the splitter's anchor for that
    position can be located verbatim (see _chunk_exercises) — this is what keeps a worker from
    having to re-scan and recount blocks in a long, repetitive document itself. A position
    whose anchor can't be located falls back to the full text, with a warning noting the
    fallback (lower reliability, not a failure). A worker that raises becomes a flagged
    placeholder exercise plus a warning — never a crash or a silent gap. The deterministic
    drop-check runs last and adds any findings to the same warnings list."""
    provider = provider or AnthropicProvider()

    split = segment(text, provider=provider)
    shell = extract_shell(text, provider=provider)
    chunks = _chunk_exercises(text, split)

    exercises: list[Exercise] = []
    uncertain_fields: list[str] = list(shell.uncertain_fields)
    warnings: list[str] = []

    for i, entry in enumerate(split.exercises):
        worker_text = chunks.get(entry.position)
        if worker_text is None:
            worker_text = text
            warnings.append(
                f"Exercise {entry.position} ({entry.name}): could not isolate its text — "
                "used the full document instead."
            )

        try:
            worker_result = extract_exercise(worker_text, entry.position, provider=provider)
        except LLMParserError as exc:
            exercises.append(_placeholder_exercise(entry.position, entry.name, str(exc)))
            warnings.append(
                f"Exercise {entry.position} ({entry.name}) failed to extract: {exc}"
            )
            continue

        exercise = Exercise(**worker_result.model_dump(exclude={"uncertain_fields"}))
        # The splitter already told us the correct position — trust that over whatever the
        # worker itself reported, rather than giving the model one more thing to get wrong.
        exercise = exercise.model_copy(update={"number": entry.position})
        exercises.append(exercise)
        uncertain_fields.extend(
            f"exercises.{i}.{path}" for path in worker_result.uncertain_fields
        )

    warnings.extend(audit(text, split, exercises))

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
