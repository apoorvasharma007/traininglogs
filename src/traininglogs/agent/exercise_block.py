from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from traininglogs.parser.parse import _parse_warmup_set_line, _parse_working_set_line

# A range ("RPE: 6-7") contributes only its upper bound — matches the convention used
# elsewhere in the AI pipeline (extraction.py's _rpe_tokens_in_text) for the same reason.
_RPE_RE = re.compile(
    r"RPE:?\s*(\d{1,2}(?:\.\d)?)(?:\s*-\s*(\d{1,2}(?:\.\d)?))?", re.IGNORECASE
)

_HEADERS = ("Warmup", "Sets", "Remarks")


@dataclass
class ParsedBlock:
    warmup_sets: List[Dict[str, Any]] = field(default_factory=list)
    sets: List[Dict[str, Any]] = field(default_factory=list)
    exercise_rpe: Optional[float] = None


def _find_header(lines: List[str], header: str, start: int = 0) -> Optional[int]:
    for i in range(start, len(lines)):
        if lines[i].strip().rstrip(":").strip() == header:
            return i
    return None


def _non_blank(lines: List[str], start: int, end: int) -> List[str]:
    return [l for l in lines[start:end] if l.strip()]


def _exercise_rpe(remarks_lines: List[str]) -> Optional[float]:
    for line in remarks_lines:
        m = _RPE_RE.search(line)
        if m:
            low, high = m.groups()
            return float(high) if high else float(low)
    return None


def parse_exercise_block(chunk: str) -> Optional[ParsedBlock]:
    """Deterministically parse one exercise's isolated chunk text into its numeric spine,
    using the same line parsers DeepTrainingParser already relies on for the markdown ingestion
    path. All-or-nothing: if the block doesn't have a 'Sets:' section with at least one
    parseable working set, or any line under 'Warmup:'/'Sets:' fails to parse (irregular
    notation — calisthenics, timed holds, band-assisted reps), returns None and the caller
    falls back to full LLM extraction for this exercise. There is no partial result."""
    lines = chunk.split("\n")

    warmup_idx = _find_header(lines, "Warmup")
    sets_idx = _find_header(lines, "Sets", start=warmup_idx + 1 if warmup_idx is not None else 0)
    if sets_idx is None:
        return None

    remarks_idx = _find_header(lines, "Remarks", start=sets_idx + 1)

    warmup_lines = _non_blank(lines, warmup_idx + 1, sets_idx) if warmup_idx is not None else []
    sets_end = remarks_idx if remarks_idx is not None else len(lines)
    working_lines = _non_blank(lines, sets_idx + 1, sets_end)
    remarks_lines = _non_blank(lines, remarks_idx + 1, len(lines)) if remarks_idx is not None else []

    if not working_lines:
        return None

    try:
        warmup_sets = [_parse_warmup_set_line(l) for l in warmup_lines]
        sets = [_parse_working_set_line(l) for l in working_lines]
    except ValueError:
        return None

    return ParsedBlock(
        warmup_sets=warmup_sets,
        sets=sets,
        exercise_rpe=_exercise_rpe(remarks_lines),
    )
