"""Turn the rep text a person wrote into the typed shape the database stores.

The model copies rep information exactly as written -- "8", "8+1", "L8/R7", "12 catches",
"feel" -- and this converts it. That division is deliberate: finding and copying is what a
language model is reliably good at, and `source_line` can prove it copied faithfully. Turning
"8+1" into {full: 8, partial: 1} is string handling, which Python does the same way every time.

It also used to be a source of real error. When the schema offered both `rep_count` and
`unilateral_rep_count`, the model had to decide which one applied, and on
"12.5 x 13 - right did partial range only" it read commentary about asymmetry as a unilateral
rep count -- filing 13 reps as right-arm-only. There is now one field and no decision to get
wrong.

Anything this cannot parse returns a warning rather than a guess. Nothing is lost: the text as
written stays on the extraction, so a parser fixed later can be re-run over stored extractions
with no model calls and no cost.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from traininglogs.models.models import RepCount, UnilateralReps

# Per-side counts. Both spellings are supported, but note which one the corpus actually uses:
# "left 8, right 7" and "left 8 + 1, right 7" appear in real logs; "L8/R7" appears nowhere.
# The short form is kept because it is the obvious thing someone would type on a phone.
_PARTIAL_GROUP = r"(\d+)(?:\s*\+\s*(\d+))?"
_UNILATERAL_WORDS = re.compile(
    rf"^left\s*{_PARTIAL_GROUP}\s*,?\s*right\s*{_PARTIAL_GROUP}$", re.IGNORECASE
)
_UNILATERAL_SHORT = re.compile(
    rf"^L\s*{_PARTIAL_GROUP}\s*/\s*R\s*{_PARTIAL_GROUP}$", re.IGNORECASE
)

# "8+1" -- full reps plus partials.
_PARTIAL = re.compile(r"^(\d+)\s*\+\s*(\d+)$")

# A leading whole number, with anything after it: "8", "12 catches", "5 attempts, 2 clean",
# "20 taps - avg 290ms". The trailing text is description, and the model has already put it in
# the set's notes; here we only need the count.
_LEADING_NUMBER = re.compile(r"^(\d+)\b")

# Written where a count would go, meaning "as many as felt right" -- common in warmups
# ("36 x feel", "0 x feel banded shoulder movement"). A real value, not a missing one, and it
# has no numeric equivalent. Matched as a leading word so a trailing description is fine.
_NO_COUNT_LEAD = re.compile(r"^(feel|amrap|max|to failure|failure)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedReps:
    """One of `rep_count` or `unilateral` is set, or neither.

    `warning` is populated only when the text looked like it should carry a count and didn't
    parse -- not when it is legitimately absent ("feel") or empty.
    """

    rep_count: Optional[RepCount] = None
    unilateral: Optional[UnilateralReps] = None
    warning: Optional[str] = None


def parse_reps(written: Optional[str]) -> ParsedReps:
    """Convert rep text as written into typed counts.

    >>> parse_reps("8").rep_count
    RepCount(full=8, partial=0)
    >>> parse_reps("8+1").rep_count
    RepCount(full=8, partial=1)
    >>> parse_reps("L8/R7").unilateral.left
    RepCount(full=8, partial=0)
    >>> parse_reps("12 catches").rep_count
    RepCount(full=12, partial=0)
    >>> parse_reps("feel").rep_count is None
    True
    """
    if written is None:
        return ParsedReps()

    text = written.strip()
    if not text:
        return ParsedReps()

    if _NO_COUNT_LEAD.match(text):
        return ParsedReps()

    for pattern in (_UNILATERAL_WORDS, _UNILATERAL_SHORT):
        m = pattern.match(text)
        if m:
            left_full, left_partial, right_full, right_partial = m.groups()
            return ParsedReps(
                unilateral=UnilateralReps(
                    left=RepCount(full=int(left_full), partial=int(left_partial or 0)),
                    right=RepCount(full=int(right_full), partial=int(right_partial or 0)),
                )
            )

    m = _PARTIAL.match(text)
    if m:
        return ParsedReps(rep_count=RepCount(full=int(m.group(1)), partial=int(m.group(2))))

    m = _LEADING_NUMBER.match(text)
    if m:
        return ParsedReps(rep_count=RepCount(full=int(m.group(1)), partial=0))

    return ParsedReps(
        warning=f"could not read a rep count from {written.strip()!r} — left unset"
    )
