from __future__ import annotations

import re
import unicodedata

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
def _rpe_tokens_in_text(text: str) -> set[float]:
    # A range ("RPE: 6-7") contributes only its upper bound — that's the value the extraction
    # convention (design session, 2026-07-26) says should land on the last set.
    return {
        float(high) if high else float(low)
        for low, high in _RPE_TOKEN_RE.findall(text)
    }


def _extracted_rpes(exercises: list[Exercise]) -> set[float]:
    return {s.rpe for ex in exercises for s in (ex.sets or []) if s.rpe is not None}


def _comparable(text: str) -> str:
    """Flatten the differences between what a person typed and what a model types back.

    Real logs contain characters a model reliably normalises when it quotes them: a curly
    apostrophe becomes a straight one, a non-breaking space becomes an ordinary space, an em
    dash becomes a hyphen. Both were found in real files on 2026-08-03 and both made a correctly
    read line look invented. Comparing exact bytes flags those as fabrications, which is a false
    alarm about the one thing this check exists to be trusted on.

    So: normalise the compatibility forms, unify the quote and dash variants NFKC leaves alone,
    and collapse runs of whitespace. What survives is the content, which is what we actually
    want to compare."""
    text = unicodedata.normalize("NFKC", text)
    for fancy, plain in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                         ("–", "-"), ("—", "-"), ("−", "-")):
        text = text.replace(fancy, plain)
    return re.sub(r"\s+", " ", text).strip()


def check_sources_are_real(chunk: str, extract: ExerciseExtract) -> list[str]:
    """Did the model read each set from a line that actually exists?

    Every entry in set_sources/warmup_sources is a verbatim quote the model claims it read a set
    from. If that quote isn't in the text, the set has no basis in the source — the model made it
    up, or copied it from an example in the prompt.

    Knows nothing about weights, units, headers or exercise types, so it works the same on
    markdown, on text off a photograph, and on a speech transcript. Comparison is on content
    rather than exact bytes -- see _comparable()."""
    warnings: list[str] = []
    haystack = _comparable(chunk)
    for kind, sources in (("set", extract.set_sources), ("warmup", extract.warmup_sources)):
        for number, line in sorted(sources.items()):
            quote = _comparable(line)
            if quote and quote not in haystack:
                warnings.append(
                    f"{kind} {number}: the source line recorded for it isn't in the text — "
                    f"this may be invented: {quote!r}"
                )
    return warnings


def check_sets_and_sources_match(extract: ExerciseExtract) -> list[str]:
    """Does every set have a source line, and every source line a set?

    A set with no source is one the model produced without pointing at anything. A source with
    no set is a line it read and then dropped. Both directions are worth knowing about."""
    warnings: list[str] = []
    pairs = (
        ("set", {str(s.number) for s in (extract.sets or [])}, extract.set_sources),
        ("warmup", {str(w.number) for w in (extract.warmup_sets or [])}, extract.warmup_sources),
    )
    for kind, numbers, sources in pairs:
        for missing in sorted(numbers - sources.keys()):
            warnings.append(f"{kind} {missing} has no source line recorded.")
        for orphan in sorted(sources.keys() - numbers):
            warnings.append(
                f"{kind} {orphan} has a source line but no matching {kind} was extracted — "
                "it may have been dropped."
            )
    return warnings


def audit(text: str, split: ExerciseSplit, exercises: list[Exercise]) -> list[str]:
    """Session-level checks: an exercise missing from the final list, or an RPE present in the
    text but absent from every set it could have landed on. Per-exercise checks live in
    check_sources_are_real() and check_sets_and_sources_match().

    A kg-token check used to sit here too. It was removed on 2026-08-04 after measuring where
    kg-suffixed numbers actually occur across all 122 input files: 1,009 of 1,036 are on
    `**Goal:**` lines and the remaining 27 are prose ("I can perhaps handle 63kg"). **None** are
    working-set weights, because sets are written `63 x 10` with no unit. So it could only ever
    fire on goal weights, which legitimately are not set weights — every warning it produced was
    noise, and it was structurally incapable of catching a dropped weight.

    The RPE check stays: sets do write `RPE 10` inline, so it can see real values, and "RPE" is
    domain vocabulary rather than a quirk of the markdown — it survives a speech transcript.

    Findings are a heuristic, not proof: a value can appear in text without being extractable
    data."""
    warnings: list[str] = []

    if len(exercises) != len(split.exercises):
        warnings.append(
            f"Exercise count mismatch: splitter found {len(split.exercises)} exercises, "
            f"but {len(exercises)} were assembled."
        )

    extracted_rpes = _extracted_rpes(exercises)
    for value in sorted(_rpe_tokens_in_text(text) - extracted_rpes):
        warnings.append(f"RPE {value} appears in the text but not in any extracted set.")

    return warnings


def assemble(text: str, provider: ExtractionProvider | None = None) -> TrainingLogLLMExtract:
    """Run the splitter, the session shell, and one worker call per exercise (sequential),
    then glue the results into a TrainingLogLLMExtract. Each worker gets an isolated,
    pre-sliced chunk of `text` for just its own exercise when the splitter's anchor for that
    position can be located verbatim (see _chunk_exercises) — this is what keeps a worker from
    having to re-scan and recount blocks in a long, repetitive document itself. A position
    whose anchor can't be located falls back to the full text, with a warning noting the
    fallback (lower reliability, not a failure).

    The model owns the numeric spine. A deterministic pre-parse used to run first on isolated
    chunks (`parse_exercise_block`, removed 2026-08-03) — measurement showed it fired on 0 of 10
    exercises in real input because it required exact-match `Warmup:`/`Sets:` headers while real
    logs use markdown (`### Working Sets`), so it had never run in production. The pure-AI path
    scores ~99.7% on the numeric spine; see `roadmap.md` for the evidence.

    A worker that raises becomes a flagged placeholder exercise plus a warning — never a crash
    or a silent gap. The deterministic drop-check runs last and adds any findings to the same
    warnings list."""
    provider = provider or AnthropicProvider()

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
        else:
            worker_text = text
            worker_position = entry.position
            warnings.append(
                f"Exercise {entry.position} ({entry.name}): could not isolate its text — "
                "used the full document instead."
            )

        try:
            worker_result = extract_exercise(worker_text, worker_position, provider=provider)
            # Checked against worker_text, which is what the model was actually shown — not the
            # whole document, or a quote from an isolated chunk would look invented whenever the
            # rest of the session happened not to contain it.
            for w in check_sources_are_real(worker_text, worker_result):
                warnings.append(f"Exercise {entry.position} ({entry.name}): {w}")
            for w in check_sets_and_sources_match(worker_result):
                warnings.append(f"Exercise {entry.position} ({entry.name}): {w}")
            exercise = Exercise(
                **worker_result.model_dump(
                    exclude={"uncertain_fields", "set_sources", "warmup_sources"}
                )
            )
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
