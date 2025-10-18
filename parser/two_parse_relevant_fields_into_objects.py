# parse_training_log_deep.py
import re, uuid
from typing import Dict, Any, Optional, List
from dataclasses import is_dataclass
from datamodels.models import (
    TrainingSession, Exercise, WarmupSet, WorkingSet, Goal, RepCount, RepRange,
    FailureTechnique, FailureTechniqueType, MyoRepDetails, LLPDetails, StaticDetails, RepQualityAssessment
)
import os, sys
# -------------------------------------------------------------------
# ✅ Add root path so imports like `parser.*` and `datamodels.*` work
# -------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

class DeepTrainingParser:
    """
    Convert intermediate dict (from TrainingMarkdownParser) into dataclass instances.
    """

    def __init__(self, parsed: Dict[str, Any]):
        self.parsed = parsed

    def build_training_session(self) -> TrainingSession:
        meta = self.parsed.get("metadata", {})
        exercises = []
        for i, ex in enumerate(self.parsed.get("exercises", []), start=1):
            exercises.append(self._parse_exercise(ex, i))

        return TrainingSession(
            data_model_version="1.0",
            data_model_type="TrainingSession",
            session_id=str(uuid.uuid4()),
            user_id="user-unknown",
            user_name="Unknown User",
            date=meta.get("date", ""),
            phase=int(meta.get("phase", 0)) if meta.get("phase") else 0,
            week=int(meta.get("week", 0)) if meta.get("week") else 0,
            is_deload_week=str(meta.get("deload", "")).lower() in ["yes", "true", "1"],
            focus=meta.get("focus", ""),
            exercises=exercises,
            session_duration_minutes=int(re.findall(r"\d+", meta.get("duration", "0"))[0]) if meta.get("duration") else 0
        )

    def _parse_exercise(self, ex: Dict[str, Any], idx: int) -> Exercise:
        name = ex.get("name", f"Exercise {idx}")
        muscles = self._split_csv(ex.get("muscles"))
        tempo = ex.get("tempo")
        goal = self._parse_goal(ex.get("goal"), ex.get("rest"))

        warmup_sets = [self._parse_warmup_set_line(l) for l in ex.get("warmup_sets", [])]
        working_sets = [self._parse_working_set_line(l) for l in ex.get("working_sets", [])]

        return Exercise(
            number=idx,
            name=name,
            working_sets=working_sets,
            target_muscle_groups=muscles,
            rep_tempo=tempo,
            current_goal=goal,
            warmup_sets=warmup_sets if warmup_sets else None,
            notes=ex.get("notes"),
            warmup_notes=ex.get("warmup_notes"),
            form_cues=ex.get("cues")
        )

    def _parse_goal(self, goal_str: Optional[str], rest_str: Optional[str]) -> Optional[Goal]:
        if not goal_str:
            return None
        m = re.search(r"([\d.]+)\s*kg\s*x\s*(\d+)\s*sets?\s*x\s*(\d+)-(\d+)\s*reps?", goal_str, re.IGNORECASE)
        if not m:
            return None
        weight, sets, rmin, rmax = m.groups()
        rest = int(re.findall(r"\d+", rest_str)[0]) if rest_str and re.findall(r"\d+", rest_str) else 0
        return Goal(weight_kg=float(weight), sets=int(sets), rep_range=RepRange(min=int(rmin), max=int(rmax)), rest_minutes=rest)

    def _parse_warmup_set_line(self, line: str) -> WarmupSet:
        m = re.match(r"^\s*(\d+)\.\s*([\d.]+)\s*x\s*([\w+-]+)?\s*-?\s*(.*)$", line)
        if not m:
            return WarmupSet(number=0, weight_kg=0.0)
        num, weight, reps, note = m.groups()
        reps_val = None
        if reps and reps.lower() not in ("feel", "na", ""):
            nm = re.match(r"(\d+)", reps)
            reps_val = int(nm.group(1)) if nm else None
        return WarmupSet(number=int(num), weight_kg=float(weight), rep_count=reps_val, notes=note.strip() if note else None)

    def _parse_working_set_line(self, line: str) -> WorkingSet:
        m_num = re.match(r"^\s*(\d+)\.\s*(.*)$", line)
        if not m_num:
            return WorkingSet(number=0, weight_kg=0.0, rep_count=RepCount(full=0))
        set_num = int(m_num.group(1))
        rest_of = m_num.group(2).strip()

        # note split (after " - ")
        note = None
        if " - " in rest_of:
            core_part, note = rest_of.split(" - ", 1)
        else:
            core_part = rest_of

        # failure extraction
        failure = None
        f_match = re.search(r"failure:\s*([a-zA-Z_]+)\s*\(\s*([^)]+)\s*\)", line, re.IGNORECASE)
        if f_match:
            failure = self._parse_failure(f_match.group(1), f_match.group(2))

        # core parse: weight x reps [+ partial] [RPE n.n] [quality]
        core_re = re.compile(
            r"([\d.]+)\s*x\s*(\d+)(?:\s*\+\s*(\d+))?\s*(?:RPE\s*([\d.]+))?\s*(?:\b(perfect|good|bad|learning)\b)?",
            re.IGNORECASE
        )
        cm = core_re.search(core_part)
        if not cm:
            simple = re.search(r"([\d.]+)\s*x\s*(\d+)", core_part)
            if not simple:
                return WorkingSet(number=set_num, weight_kg=0.0, rep_count=RepCount(full=0))
            weight = float(simple.group(1)); full = int(simple.group(2))
            return WorkingSet(number=set_num, weight_kg=weight, rep_count=RepCount(full=full), notes=note, failure_technique=failure)

        weight_s, full_s, partial_s, rpe_s, quality_s = cm.groups()
        weight = float(weight_s)
        full = int(full_s)
        partial = int(partial_s) if partial_s else 0
        rpe = float(rpe_s) if rpe_s else None
        quality = self._parse_quality(quality_s)

        return WorkingSet(
            number=set_num,
            weight_kg=weight,
            rep_count=RepCount(full=full, partial=partial),
            rpe=rpe,
            rep_quality_assessment=quality,
            notes=note,
            failure_technique=failure
        )

    def _parse_failure(self, kind: str, inner: str) -> FailureTechnique:
        k = kind.lower()
        if k in ("myo", "myo_reps", "myoreps"):
            parts = [p.strip() for p in re.split(r",\s*", inner) if p.strip()]
            mini_sets = []
            for i, p in enumerate(parts, start=1):
                pm = re.match(r"(\d+)\+?(\d+)?", p)
                if pm:
                    full = int(pm.group(1))
                    partial = int(pm.group(2)) if pm.group(2) else 0
                else:
                    full = int(re.findall(r"\d+", p)[0]); partial = 0
                mini_sets.append({"miniSet": i, "repCount": RepCount(full=full, partial=partial)})
            return FailureTechnique(technique_type=FailureTechniqueType.MYO_REPS, details=MyoRepDetails(mini_sets=mini_sets))

        if k in ("llp",):
            n = int(re.findall(r"\d+", inner)[0])
            return FailureTechnique(technique_type=FailureTechniqueType.LLP, details=LLPDetails(partial_rep_count=n))

        if k in ("static",):
            s = int(re.findall(r"\d+", inner)[0])
            return FailureTechnique(technique_type=FailureTechniqueType.STATIC, details=StaticDetails(hold_duration_seconds=s))

        raise ValueError(f"Unknown failure technique: {kind}")

    def _parse_quality(self, q):
        if not q:
            return None
        try:
            return RepQualityAssessment(q.lower())
        except Exception:
            return None

    def _split_csv(self, s):
        if not s:
            return None
        return [x.strip() for x in s.split(",") if x.strip()]