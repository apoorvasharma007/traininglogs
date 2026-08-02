from __future__ import annotations

import os
import re

from pydantic import ValidationError

from traininglogs.agent.exercise_block import ParsedBlock, parse_exercise_block
from traininglogs.agent.prompts import (
    LABELS_SYSTEM_PROMPT,
    SHELL_SYSTEM_PROMPT,
    SPLITTER_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    WORKER_SYSTEM_PROMPT,
)
from traininglogs.agent.providers import AnthropicProvider, ExtractionProvider
from traininglogs.agent.schemas import (
    ExerciseExtract,
    ExerciseLabelsExtract,
    ExercisePosition,
    ExerciseSplit,
    LLMParserError,
    SessionShellExtract,
    TrainingLogLLMExtract,
)
from traininglogs.models.models import Exercise, WarmupSet, WorkingSet

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

LABELS_TOOL_NAME = "extract_exercise_labels"
LABELS_TOOL_DESCRIPTION = (
    "Classify the exercise and capture its notes — its sets were already read deterministically."
)


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


def extract_exercise_labels(
    text: str,
    position: int,
    set_numbers: list[int],
    provider: ExtractionProvider | None = None,
) -> ExerciseLabelsExtract:
    """Extract only the classification/free-text fields for the exercise at `position` —
    used in place of extract_exercise() when parse_exercise_block() already supplied this
    exercise's numeric spine deterministically. `text` is always the isolated chunk for this
    one exercise; this path never runs on the full-text fallback (see assemble())."""
    provider = provider or AnthropicProvider()
    tool_schema = ExerciseLabelsExtract.model_json_schema()
    numbers_str = ", ".join(str(n) for n in set_numbers)
    prompt = (
        f"Extract exercise number {position}. Its sets have already been read from the text "
        f"and are numbered {numbers_str} — do not re-extract, restate, or count the sets "
        f"themselves; classify the exercise and capture any notes only.\n\nText:\n{text}"
    )

    raw = provider.extract(
        prompt, tool_schema, LABELS_SYSTEM_PROMPT, LABELS_TOOL_NAME, LABELS_TOOL_DESCRIPTION
    )

    try:
        return ExerciseLabelsExtract.model_validate(raw)
    except ValidationError as exc:
        raise LLMParserError(
            f"Exercise {position} label extraction did not pass validation:\n{exc}"
        ) from exc


# Sentinel prefix identifying a placeholder Exercise's notes field. Owned here and read by
# validation_card_builder.py to flag the exercise on the confirmation card — deliberately not
# a new field on the Exercise model itself, since that model's blast radius (DB, API) extends
# well beyond the AI-parser confirmation flow this refactor is scoped to.
PLACEHOLDER_NOTE_PREFIX = "Extraction failed for this exercise:"

# Escape hatch that turns the parse-first fast path off, so the model does the full extraction
# for every exercise. Measurement only — see assemble()'s docstring.
DISABLE_PARSE_FIRST_ENV_VAR = "TRAININGLOGS_DISABLE_PARSE_FIRST"


def _placeholder_exercise(position: int, name: str, error: str) -> Exercise:
    return Exercise(
        number=position,
        name=name,
        notes=f"{PLACEHOLDER_NOTE_PREFIX} {error}",
    )


# Deliberately 0, not a safety margin. A chunk already runs up to (not including) the next
# exercise's own anchor line, and by construction everything belonging to the current exercise
# (its remarks included) appears before that line — so a positive value here only ever leaks
# the start of the next exercise (its name + first warmup line) into the current chunk. That
# leak was the root cause of a "lost in the middle"-looking failure that was actually a
# deterministic bug: a worker handed a 2-exercise excerpt but told to extract "exercise number
# N" (the global split position) would count blocks in the leaked fragment and misfire — see
# assemble(), which now passes position 1 (not the global position) whenever a chunk was
# successfully isolated, precisely because an isolated chunk contains exactly one exercise.
CHUNK_TRAILING_OVERLAP_LINES = 0


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


def _place_exercise_rpe(
    sets: list[WorkingSet], exercise_rpe: float | None, target_set: int | None
) -> tuple[list[WorkingSet], int | None]:
    """Place a whole-exercise RPE (ParsedBlock.exercise_rpe — deterministic value, ambiguous
    placement) onto one set. Defaults to the last set, matching the full-extraction path's own
    last-set convention, unless the LLM named a different, valid set number. Never overwrites a
    set's own already-parsed inline RPE (e.g. "1. 90kg x 8 RPE 7" parses its RPE directly, with
    no placement ambiguity at all). Returns the possibly-updated set list and the set number the
    value actually landed on, or None if every candidate already had its own RPE."""
    if exercise_rpe is None or not sets:
        return sets, None
    valid_numbers = {s.number for s in sets}
    number = target_set if target_set in valid_numbers else sets[-1].number
    updated: list[WorkingSet] = []
    placed_number: int | None = None
    for s in sets:
        if s.number == number and s.rpe is None:
            updated.append(s.model_copy(update={"rpe": exercise_rpe}))
            placed_number = number
        else:
            updated.append(s)
    return updated, placed_number


def _build_parsed_exercise(
    entry: ExercisePosition, parsed: ParsedBlock, labels: ExerciseLabelsExtract
) -> tuple[Exercise, list[str], list[str]]:
    """Combine a ParsedBlock (numeric spine, deterministic) with an ExerciseLabelsExtract
    (classification + notes, LLM) into a final Exercise. The LLM's schema never had sets or
    warmup_sets fields, so there is nothing here to reconcile or arbitrate — every set/warmup
    entry comes from `parsed`, unconditionally. Returns (exercise, uncertain_fields, warnings);
    uncertain_fields uses dot-paths relative to this exercise, matching the full-extraction
    path's convention."""
    try:
        sets = [WorkingSet(**s) for s in parsed.sets]
        warmup_sets = [WarmupSet(**w) for w in parsed.warmup_sets] or None
    except ValidationError as exc:
        raise LLMParserError(
            f"Exercise {entry.position} ({entry.name}): parsed set data failed validation:\n{exc}"
        ) from exc

    uncertain: list[str] = list(labels.uncertain_fields)
    warnings: list[str] = []

    valid_numbers = {s.number for s in sets}
    for key, note in labels.set_notes.items():
        try:
            number = int(key)
        except ValueError:
            number = None
        if number not in valid_numbers:
            warnings.append(
                f"Exercise {entry.position} ({entry.name}): a set note was keyed to set "
                f"{key!r}, which doesn't exist among this exercise's sets — dropped."
            )
            continue
        sets = [s.model_copy(update={"notes": note}) if s.number == number else s for s in sets]

    sets, placed_number = _place_exercise_rpe(
        sets, parsed.exercise_rpe, labels.exercise_rpe_target_set
    )
    if parsed.exercise_rpe is not None:
        if placed_number is not None:
            uncertain.append(f"sets.{placed_number}.rpe")
        else:
            warnings.append(
                f"Exercise {entry.position} ({entry.name}): exercise-level RPE "
                f"{parsed.exercise_rpe} could not be placed — every candidate set already had "
                "its own RPE."
            )

    exercise = Exercise(
        number=entry.position,
        name=labels.name,
        tags=labels.tags,
        modality=labels.modality,
        movement_pattern=labels.movement_pattern,
        sets=sets,
        target_muscle_groups=labels.target_muscle_groups,
        rep_tempo=labels.rep_tempo,
        current_goal=labels.current_goal,
        warmup_sets=warmup_sets,
        notes=labels.notes,
        warmup_notes=labels.warmup_notes,
        form_cues=labels.form_cues,
    )
    return exercise, uncertain, warnings


def assemble(
    text: str,
    provider: ExtractionProvider | None = None,
    use_parse_first: bool | None = None,
) -> TrainingLogLLMExtract:
    """Run the splitter, the session shell, and one worker call per exercise (sequential),
    then glue the results into a TrainingLogLLMExtract. Each worker gets an isolated,
    pre-sliced chunk of `text` for just its own exercise when the splitter's anchor for that
    position can be located verbatim (see _chunk_exercises) — this is what keeps a worker from
    having to re-scan and recount blocks in a long, repetitive document itself. A position
    whose anchor can't be located falls back to the full text, with a warning noting the
    fallback (lower reliability, not a failure), and always uses the full-extraction path below
    (parse_exercise_block is never attempted against a non-isolated chunk).

    When a chunk IS isolated, parse_exercise_block() runs first (extraction-accuracy fix,
    parse-first design — see extraction-accuracy-plan.md). If it fully parses the block, the
    numeric spine (sets, warmup_sets) comes from the parser and the worker call only classifies
    the exercise (extract_exercise_labels — narrow schema, no sets/warmup_sets fields at all).
    If it can't parse the block (irregular notation), the worker does the full job itself via
    extract_exercise(), exactly as before this fix.

    A worker that raises becomes a flagged placeholder exercise plus a warning — never a crash
    or a silent gap. The deterministic drop-check runs last and adds any findings to the same
    warnings list.

    `use_parse_first=False` (or DISABLE_PARSE_FIRST_ENV_VAR=1) skips parse_exercise_block()
    entirely, so every exercise goes down the full extract_exercise() path and the model owns
    the numeric spine. That is a strictly less reliable pipeline — it exists to measure model
    capability in isolation, not as a production mode."""
    provider = provider or AnthropicProvider()
    if use_parse_first is None:
        use_parse_first = os.environ.get(DISABLE_PARSE_FIRST_ENV_VAR) != "1"

    split = segment(text, provider=provider)
    shell = extract_shell(text, provider=provider)
    chunks = _chunk_exercises(text, split)

    exercises: list[Exercise] = []
    uncertain_fields: list[str] = list(shell.uncertain_fields)
    warnings: list[str] = []

    for i, entry in enumerate(split.exercises):
        chunk_text = chunks.get(entry.position)
        if chunk_text is not None:
            # An isolated chunk contains exactly this one exercise — position 1, not the
            # global split position, which would only make sense against the full document.
            worker_text = chunk_text
            worker_position = 1
            parsed = parse_exercise_block(chunk_text) if use_parse_first else None
        else:
            worker_text = text
            worker_position = entry.position
            parsed = None
            warnings.append(
                f"Exercise {entry.position} ({entry.name}): could not isolate its text — "
                "used the full document instead."
            )

        try:
            if parsed is not None:
                set_numbers = [s["number"] for s in parsed.sets]
                labels = extract_exercise_labels(
                    worker_text, worker_position, set_numbers, provider=provider
                )
                exercise, exercise_uncertain, exercise_warnings = _build_parsed_exercise(
                    entry, parsed, labels
                )
                warnings.extend(exercise_warnings)
            else:
                worker_result = extract_exercise(worker_text, worker_position, provider=provider)
                exercise = Exercise(**worker_result.model_dump(exclude={"uncertain_fields"}))
                # The splitter already told us the correct position — trust that over whatever
                # the worker itself reported, rather than giving the model one more thing to
                # get wrong.
                exercise = exercise.model_copy(update={"number": entry.position})
                exercise_uncertain = worker_result.uncertain_fields
        except LLMParserError as exc:
            exercises.append(_placeholder_exercise(entry.position, entry.name, str(exc)))
            warnings.append(
                f"Exercise {entry.position} ({entry.name}) failed to extract: {exc}"
            )
            continue

        exercises.append(exercise)
        uncertain_fields.extend(
            f"exercises.{i}.{path}" for path in exercise_uncertain
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
