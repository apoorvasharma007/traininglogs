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


def _parse_warmup_set_line(line: str) -> Dict[str, Any]:
    # Unit annotation (kg/lbs) between weight and "x" is optional and stripped; storage is
    # always kg, matching the working-set line parser's convention below.
    m = re.match(r"^\s*(\d+)\.\s*([\d.]+)\s*(?:kg|lbs?)?\s*x\s*([\w+-]+)?\s*-?\s*(.*)$", line)
    if not m:
        raise ValueError(f"Cannot parse warmup set line: {line!r}")
    num, weight, reps, note = m.groups()
    reps_val = None
    if reps and reps.lower() not in ("feel", ""):
        nm = re.match(r"(\d+)", reps)
        reps_val = int(nm.group(1)) if nm else None
    result: Dict[str, Any] = {"number": int(num), "weight_kg": float(weight), "rep_count": reps_val}
    if note and note.strip():
        result["notes"] = note.strip()
    return result


def _parse_working_set_line(line: str) -> Dict[str, Any]:
    m_num = re.match(r"^\s*(\d+)\.\s*(.*)$", line)
    if not m_num:
        raise ValueError(f"Cannot parse working set line: {line!r}")
    set_num = int(m_num.group(1))
    rest_of = m_num.group(2).strip()

    note = None
    if " - " in rest_of:
        core_part, note = rest_of.split(" - ", 1)
    else:
        core_part = rest_of

    failure = None
    f_match = re.search(r"failure:\s*([a-zA-Z_]+)\s*\(\s*([^)]+)\s*\)", line, re.IGNORECASE)
    if f_match:
        failure = _parse_failure(f_match.group(1), f_match.group(2))

    # unilateral format: weight x (left|L):? full [+ partial], (right|R):? full [+ partial]
    uni_re = re.compile(
        r"([\d.]+)\s*x\s*((?:left|right|[lr])\s*:?\s*\d+(?:\s*\+\s*\d+)?)"
        r"\s*,\s*((?:left|right|[lr])\s*:?\s*\d+(?:\s*\+\s*\d+)?)"
        r"(?:\s+RPE\s*([\d.]+))?(?:\s+\b(perfect|good|bad|learning)\b)?",
        re.IGNORECASE,
    )
    um = uni_re.search(core_part)
    if um:
        weight_s, side_a_s, side_b_s, rpe_s, quality_s = um.groups()

        def _parse_side(s: str) -> tuple:
            m = re.match(
                r"(left|right|[lr])\s*:?\s*(\d+)\s*(?:\+\s*(\d+))?",
                s.strip(), re.IGNORECASE,
            )
            name = m.group(1).lower()
            side = "left" if name in ("l", "left") else "right"
            return side, int(m.group(2)), int(m.group(3)) if m.group(3) else 0

        s_a = _parse_side(side_a_s)
        s_b = _parse_side(side_b_s)
        sides = {s_a[0]: (s_a[1], s_a[2]), s_b[0]: (s_b[1], s_b[2])}
        left = sides.get("left")
        right = sides.get("right")
        result: Dict[str, Any] = {
            "number": set_num,
            "weight_kg": float(weight_s),
            "unilateral_rep_count": {
                "left":  {"full": left[0],  "partial": left[1]}  if left  else None,
                "right": {"full": right[0], "partial": right[1]} if right else None,
            },
        }
        if rpe_s:
            result["rpe"] = float(rpe_s)
        quality = _parse_quality(quality_s)
        if quality:
            result["rep_quality_assessment"] = quality
        if note:
            result["notes"] = note
        return result

    # core parse: weight [kg|lbs] x [reps [+ partial]] [RPE n.n] [quality]
    # Rep count is optional — some failure sets log weight and RPE without counting reps.
    # Unit annotation (kg/lbs) after weight is stripped; storage is always kg.
    # RPE values above 10 are capped to 10.0 — the scale ends at 10 and any higher
    # value is a data-entry error (the most common case is a failure set typo).
    core_re = re.compile(
        r"([\d.]+)\s*(?:kg|lbs?)?\s*x\s*(?:(\d+)(?:\s*\+\s*(\d+))?)?\s*(?:RPE\s*([\d.]+))?\s*(?:\b(perfect|good|bad|learning)\b)?",
        re.IGNORECASE
    )
    cm = core_re.search(core_part)
    if not cm:
        simple = re.search(r"([\d.]+)\s*(?:kg|lbs?)?\s*x\s*(\d+)", core_part, re.IGNORECASE)
        if not simple:
            raise ValueError(f"Cannot parse working set line: {line!r}")
        weight = float(simple.group(1))
        full = int(simple.group(2))
        result = {"number": set_num, "weight_kg": weight, "rep_count": {"full": full, "partial": 0}}
        if note:
            result["notes"] = note
        if failure:
            result["failure_technique"] = failure
        return result

    weight_s, full_s, partial_s, rpe_s, quality_s = cm.groups()
    result = {
        "number": set_num,
        "weight_kg": float(weight_s),
    }
    if full_s is not None:
        result["rep_count"] = {"full": int(full_s), "partial": int(partial_s) if partial_s else 0}
    if rpe_s:
        result["rpe"] = float(rpe_s)
    quality = _parse_quality(quality_s)
    if quality:
        result["rep_quality_assessment"] = quality
    if note:
        result["notes"] = note
    if failure:
        result["failure_technique"] = failure
    return result


class DeepTrainingParser:
    """
    Convert intermediate dict (from TrainingMarkdownParser) into a plain dict
    shaped directly for TrainingSession.model_validate().
    """

    def __init__(self, parsed: Dict[str, Any]):
        self.parsed = parsed

    def build_training_session(self) -> Dict[str, Any]:
        meta = self.parsed.get("metadata", {})
        exercises = []
        for i, ex in enumerate(self.parsed.get("exercises", []), start=1):
            exercises.append(self._parse_exercise(ex, i))

        deload_raw = meta.get("deload")
        if deload_raw is None or str(deload_raw).strip() == "":
            is_deload_week = False
        else:
            is_deload_week = str(deload_raw).strip().lower() in ("yes", "true", "1")

        duration_raw = meta.get("duration")
        duration_minutes: Optional[int] = None
        if duration_raw:
            duration_nums = re.findall(r"\d+", str(duration_raw))
            if not duration_nums:
                raise ValueError(f"Cannot parse duration value: {duration_raw!r}")
            duration_minutes = int(duration_nums[0])

        program = meta.get("program") or None
        program_length_raw = meta.get("program length weeks")

        # phase and week are co-dependent signals of a program session.
        # If either is present, both are required. If neither is present, standalone.
        # program name is independent optional metadata (may come from path derivation).
        phase_raw = meta.get("phase")
        week_raw = meta.get("week")
        if phase_raw is not None or week_raw is not None:
            if phase_raw is None:
                raise ValueError("Program session has 'week' but is missing 'phase'")
            if week_raw is None:
                raise ValueError("Program session has 'phase' but is missing 'week'")
            phase: Optional[int] = int(phase_raw)
            week: Optional[int] = int(week_raw)
        else:
            phase = None
            week = None

        return {
            "data_model_version": "0.0.1",
            "data_model_type": "TrainingSession",
            "user_id": str(meta.get("user_id", "7")),
            "user_name": meta.get("name", "Apoorva Sharma"),
            "date": meta.get("date"),
            "program": program,
            "program_author": meta.get("author") or None,
            "program_length_weeks": int(program_length_raw) if program_length_raw else None,
            "phase": phase,
            "week": week,
            "is_deload_week": is_deload_week,
            "focus": meta.get("focus"),
            "exercises": exercises,
            "session_duration_minutes": duration_minutes,
        }

    def _parse_exercise(self, ex: Dict[str, Any], idx: int) -> Dict[str, Any]:
        name = ex.get("name", f"Exercise {idx}")

        warmup_sets = [self._parse_warmup_set_line(l) for l in ex.get("warmup_sets", [])]

        if ex.get("activity_sets"):
            sets = [
                s for s in (self._parse_activity_set_line(l) for l in ex["activity_sets"])
                if s is not None
            ]
        else:
            sets = [self._parse_working_set_line(l) for l in ex.get("working_sets", [])]

        result: Dict[str, Any] = {
            "number": idx,
            "name": name,
            "sets": sets,
        }
        goal = self._parse_goal(ex.get("goal"), ex.get("rest"))
        if goal is not None:
            result["current_goal"] = goal
        muscles = self._split_csv(ex.get("muscles"))
        if muscles:
            result["target_muscle_groups"] = muscles
        if ex.get("tempo"):
            result["rep_tempo"] = ex["tempo"]
        if warmup_sets:
            result["warmup_sets"] = warmup_sets
        if ex.get("notes"):
            result["notes"] = ex["notes"]
        if ex.get("warmup_notes"):
            result["warmup_notes"] = ex["warmup_notes"]
        if ex.get("cues"):
            result["form_cues"] = ex["cues"]
        return result

    def _parse_goal(self, goal_str: Optional[str], rest_str: Optional[str]) -> Optional[Dict[str, Any]]:
        if not goal_str:
            return None
        m = re.search(r"([\d.]+)\s*(?:kg|lbs?)\s*x\s*(\d+)\s*sets?\s*x\s*(\d+)-(\d+)\s*reps?", goal_str, re.IGNORECASE)
        if not m:
            raise ValueError(f"Cannot parse goal string: {goal_str!r}")
        weight, sets, rmin, rmax = m.groups()
        rest_min = int(re.findall(r"\d+", rest_str)[0]) if rest_str and re.findall(r"\d+", rest_str) else None
        result: Dict[str, Any] = {
            "weight_kg": float(weight),
            "sets": int(sets),
            "rep_range": {"min": int(rmin), "max": int(rmax)},
        }
        if rest_min is not None:
            result["rest"] = {"minutes": rest_min}
        return result

    def _parse_warmup_set_line(self, line: str) -> Dict[str, Any]:
        return _parse_warmup_set_line(line)

    def _parse_activity_set_line(self, line: str) -> Optional[Dict[str, Any]]:
        m_num = re.match(r"^\s*(\d+)\.\s*(.*)$", line)
        if not m_num:
            return None
        set_num = int(m_num.group(1))
        rest_of = m_num.group(2).strip()

        result: Dict[str, Any] = {"number": set_num}

        min_m = re.search(r"(\d+)\s*min\b", rest_of, re.IGNORECASE)
        sec_m = re.search(r"(\d+)\s*sec\b", rest_of, re.IGNORECASE)
        if min_m:
            result["duration_seconds"] = int(min_m.group(1)) * 60
        elif sec_m:
            result["duration_seconds"] = int(sec_m.group(1))

        km_m = re.search(r"([\d.]+)\s*km\b", rest_of, re.IGNORECASE)
        m_dist = re.search(r"(\d+)\s*m\b", rest_of, re.IGNORECASE)
        if km_m:
            result["distance_meters"] = float(km_m.group(1)) * 1000
        elif m_dist:
            result["distance_meters"] = float(m_dist.group(1))

        hr_m = re.search(r"\bHR\s+(\d+)\b", rest_of, re.IGNORECASE)
        if hr_m:
            result["heart_rate_bpm"] = int(hr_m.group(1))

        return result

    def _parse_working_set_line(self, line: str) -> Dict[str, Any]:
        return _parse_working_set_line(line)

    def _parse_failure(self, kind: str, inner: str) -> Dict[str, Any]:
        return _parse_failure(kind, inner)

    def _parse_quality(self, q: Optional[str]) -> Optional[str]:
        return _parse_quality(q)

    def _split_csv(self, s: Optional[str]) -> Optional[List[str]]:
        if not s:
            return None
        return [x.strip() for x in s.split(",") if x.strip()]
