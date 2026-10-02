"""Which fields get corrected most -- from the `extractions.corrections` log.

Every change a person makes before confirming is recorded there, by source: "manual" (edited on
the card) or "ai" (a typed correction the model turned into edits). Records written before
`source` existed came from the typed-correction path, so they count as "ai". Pure functions: the
caller loads the records, this module only counts.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

_POSITION = re.compile(r"(?<=\.)\d+(?=\.|$)|^\d+(?=\.|$)")


# A working set's reps are one value on the card but two fields in the extract -- a reps edit
# always writes both (one filled, one null). Counted as the one card field it was.
_REPS_FIELDS = re.compile(r"^(exercises\.\d+\.sets\.\d+)\.(rep_count|unilateral_rep_count)$")


def path_pattern(path: str) -> str:
    """'exercises.3.sets.1.rpe' -> 'exercises.*.sets.*.rpe'."""
    return _POSITION.sub("*", path)


def _card_field_path(path: str) -> str:
    """A working set's rep_count / unilateral_rep_count -> its `reps`; anything else as is."""
    m = _REPS_FIELDS.match(path)
    return f"{m.group(1)}.reps" if m else path


@dataclass
class PatternCount:
    pattern: str
    by_source: Counter = field(default_factory=Counter)
    sessions: set[str] = field(default_factory=set)

    @property
    def total(self) -> int:
        return sum(self.by_source.values())


@dataclass
class CorrectionSummary:
    fields: list[PatternCount]
    ops: Counter
    sessions_with_corrections: int
    sessions_total: int


def summarize(corrections_by_extraction: dict[str, list[dict]]) -> CorrectionSummary:
    """Count field edits by path pattern and source, and add/remove ops by type.

    `corrections_by_extraction` maps an extraction id to its stored corrections list. An op
    record's edits (the whole new list) are not counted as field edits -- the op itself is
    what happened, and it is counted under `ops`.
    """
    patterns: dict[str, PatternCount] = defaultdict(lambda: PatternCount(pattern=""))
    ops: Counter = Counter()

    for extraction_id, records in corrections_by_extraction.items():
        for record in records or []:
            if "op" in record:
                ops[record["op"]] += 1
                continue
            source = record.get("source", "ai")
            paths = {_card_field_path(edit["path"]) for edit in record.get("edits", [])}
            for path in sorted(paths):
                pattern = path_pattern(path)
                entry = patterns[pattern]
                entry.pattern = pattern
                entry.by_source[source] += 1
                entry.sessions.add(extraction_id)

    return CorrectionSummary(
        fields=sorted(patterns.values(), key=lambda p: (-p.total, p.pattern)),
        ops=ops,
        sessions_with_corrections=sum(1 for r in corrections_by_extraction.values() if r),
        sessions_total=len(corrections_by_extraction),
    )
