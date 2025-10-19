# parse_training_log_deep.py
import re, uuid
from typing import Dict, Any, Optional, List
from dataclasses import is_dataclass
from data_class_model.models import (
    TrainingSession, Exercise, WarmupSet, WorkingSet, Goal, RepCount, RepRange,
    FailureTechnique, FailureTechniqueType, MyoRepDetails, LLPDetails, StaticDetails, RepQualityAssessment, MyoRep,
    DropSet, DropSetDetails
)
import os, sys
# -------------------------------------------------------------------
# ✅ Add root path so imports like `parser.*` and `datamodels.*` work
# -------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# TODO: add more validations and error hadling wherever we are returning None currently and all the TODOs mentioned in the code below
# TODO: we can use ValueError or custom exceptions to handle errors in parsing and validation

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

        deload_raw = meta.get("deload")
        if deload_raw is None or str(deload_raw).strip() == "":
            is_deload_week = "false"
        else:
            is_deload_week = str(deload_raw).strip().lower() in ("yes", "true", "1")
        
        ## THIS IS WHERE WE ARE SETTING UP THE DEFAULTS FOR TRAINING OBJECT FOR NOW..
        ## TODO: WE WIL MOVE THIS INFO OUT TO ITS OWN MODULE LATER, A MODULE FOR DEFAULT VALUES.
        
        # build a deterministic session id from date + focus + user_id (fallback to uuid if not enough info)
        user_id_val = str(meta.get("user_id", "7"))
        date_val = meta.get("date", "")
        focus_val = meta.get("focus", "")

        def _clean(s: Optional[str]) -> str:
            if not s:
                return ""
                # keep only alphanumerics, dash and underscore; collapse spaces to dash; lowercase
            return re.sub(r"[^A-Za-z0-9_-]+", "-", str(s).strip()).strip("-").lower()

        combined_parts = [p for p in (_clean(date_val), _clean(focus_val), user_id_val) if p]
        if combined_parts:
            session_id = "_".join(combined_parts)
        else:
            session_id = str(uuid.uuid4())

        return TrainingSession(
            data_model_version="0.0.1",
            data_model_type="TrainingSession",
            session_id=session_id,
            user_id=user_id_val,
            user_name=meta.get("name", "Apoorva Sharma"),
            date=meta.get("date"),
            program=meta.get("program", "BODYBUILDING TRANSFORMATION SYSTEM"),
            program_author=meta.get("author", "Jeff Nippard"),
            program_length_weeks=int(meta.get("program length weeks", 12)),
            phase=int(meta.get("phase")),
            week=int(meta.get("week")),
            is_deload_week=is_deload_week,
            focus=meta.get("focus"),
            exercises=exercises,
            session_duration_minutes=int(re.findall(r"\d+", meta.get("duration"))[0])
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
            notes=ex.get("notes"), # TODO: get method saves me here but i should explicitly handle missing keys by returning None
            warmup_notes=ex.get("warmup_notes"),
            form_cues=ex.get("cues")
        )

    def _parse_goal(self, goal_str: Optional[str], rest_str: Optional[str]) -> Optional[Goal]:
        if not goal_str:
            return None
        m = re.search(r"([\d.]+)\s*kg\s*x\s*(\d+)\s*sets?\s*x\s*(\d+)-(\d+)\s*reps?", goal_str, re.IGNORECASE)
        # TODO: this returning None will cause an error later; add validation
        if not m:
            return None
        weight, sets, rmin, rmax = m.groups()
        rest = int(re.findall(r"\d+", rest_str)[0]) if rest_str and re.findall(r"\d+", rest_str) else None
        # TODO: this will thrown an error if weight_kg , sets, rmin, rmax are None from regex; add validation
        return Goal(weight_kg=float(weight), sets=int(sets), rep_range=RepRange(min=int(rmin), max=int(rmax)), rest_minutes=rest)

    def _parse_warmup_set_line(self, line: str) -> Optional[WarmupSet]:
        m = re.match(r"^\s*(\d+)\.\s*([\d.]+)\s*x\s*([\w+-]+)?\s*-?\s*(.*)$", line)
        if not m:
            # TODO: we should handle and log this error here itself in the parser cuz returning None will cause an error later; add validation
            return None
        num, weight, reps, note = m.groups()
        reps_val = None
        if reps and reps.lower() not in ("feel", ""):
            nm = re.match(r"(\d+)", reps)
            reps_val = int(nm.group(1)) if nm else None
        return WarmupSet(number=int(num), weight_kg=float(weight), rep_count=reps_val, notes=note.strip() if note else None)

    def _parse_working_set_line(self, line: str) -> WorkingSet:
        m_num = re.match(r"^\s*(\d+)\.\s*(.*)$", line)
        if not m_num:
            # TODO: we should handle and log this error here itself in the parser cuz returning None will cause an error later; add validation
            return None
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
                # create MyoRep instances (snake_case) so MyoRepDetails normalizes correctly
                mini_sets.append(MyoRep(number=i, rep_count=RepCount(full=full, partial=partial)))
            return FailureTechnique(technique_type=FailureTechniqueType.MYO_REPS, details=MyoRepDetails(mini_sets=mini_sets))

        if k in ("llp",):
            n = int(re.findall(r"\d+", inner)[0])
            return FailureTechnique(technique_type=FailureTechniqueType.LLP, details=LLPDetails(partial_rep_count=n))

        # Support the new keyword 'statichold' used in the markdown template.
        # Keep 'static' and a couple of common variants for backward compatibility.
        if k in ("static", "statichold", "static_hold", "static-hold"):
            s = int(re.findall(r"\d+", inner)[0])
            return FailureTechnique(technique_type=FailureTechniqueType.STATIC, details=StaticDetails(hold_duration_seconds=s))

        if k in ("dropset", "drop_set", "drop-set"):
            # parse entries like: 90 x 8, 85 x 5, 75 x 6 + 1
            parts = [p.strip() for p in re.split(r",\s*", inner) if p.strip()]
            drop_sets = []
            for i, p in enumerate(parts, start=1):
                m = re.match(r"([\d.]+)\s*x\s*(\d+)(?:\s*\+\s*(\d+))?", p)
                if not m:
                    # fallback: try to extract numbers
                    nums = re.findall(r"[\d.]+", p)
                    if len(nums) >= 2:
                        weight = float(nums[0]); full = int(nums[1]); partial = int(nums[2]) if len(nums) > 2 else 0
                    else:
                        raise ValueError(f"Invalid dropset entry: {p}")
                else:
                    weight = float(m.group(1)); full = int(m.group(2)); partial = int(m.group(3)) if m.group(3) else 0
                drop_sets.append(DropSet(number=i, weight_kg=weight, rep_count=RepCount(full=full, partial=partial)))
            return FailureTechnique(technique_type=FailureTechniqueType.DROP_SET, details=DropSetDetails(drop_sets=drop_sets))

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