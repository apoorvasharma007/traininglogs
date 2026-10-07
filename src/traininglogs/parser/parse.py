"""Reading a set's quality word and failure-technique notes; used by agent/schemas.py."""
import re
from typing import Any, Dict, List, Optional


def _parse_quality(q: Optional[str]) -> Optional[str]:
    if not q:
        return None
    q = q.lower()
    if q in ("good", "bad", "perfect", "learning"):
        return q
    return None


def _parse_failure(kind: str, inner: str) -> Dict[str, Any]:
    k = kind.lower()
    if k in ("myo", "myo_reps", "myoreps"):
        parts = [p.strip() for p in re.split(r",\s*", inner) if p.strip()]
        mini_sets: List[Dict[str, Any]] = []
        for i, p in enumerate(parts, start=1):
            pm = re.match(r"(\d+)\+?(\d+)?", p)
            if pm:
                full = int(pm.group(1))
                partial = int(pm.group(2)) if pm.group(2) else 0
            else:
                full = int(re.findall(r"\d+", p)[0])
                partial = 0
            mini_sets.append({"number": i, "rep_count": {"full": full, "partial": partial}})
        return {"technique_type": "MyoReps", "details": {"mini_sets": mini_sets}}

    if k in ("llp",):
        n = int(re.findall(r"\d+", inner)[0])
        return {"technique_type": "LLP", "details": {"partial_rep_count": n}}

    if k in ("static", "statichold", "static_hold", "static-hold"):
        s = int(re.findall(r"\d+", inner)[0])
        return {"technique_type": "StaticHold", "details": {"hold_duration_seconds": s}}

    if k in ("dropset", "drop_set", "drop-set"):
        parts = [p.strip() for p in re.split(r",\s*", inner) if p.strip()]
        drop_sets: List[Dict[str, Any]] = []
        for i, p in enumerate(parts, start=1):
            m = re.match(r"([\d.]+)\s*x\s*(\d+)(?:\s*\+\s*(\d+))?", p)
            if not m:
                nums = re.findall(r"[\d.]+", p)
                if len(nums) >= 2:
                    weight = float(nums[0])
                    full = int(nums[1])
                    partial = int(nums[2]) if len(nums) > 2 else 0
                else:
                    raise ValueError(f"Invalid dropset entry: {p}")
            else:
                weight = float(m.group(1))
                full = int(m.group(2))
                partial = int(m.group(3)) if m.group(3) else 0
            drop_sets.append({"number": i, "weight_kg": weight, "rep_count": {"full": full, "partial": partial}})
        return {"technique_type": "DropSet", "details": {"drop_sets": drop_sets}}

    raise ValueError(f"Unknown failure technique: {kind}")
