import sys
import pathlib
import pytest

# Ensure the workspace root is on sys.path so tests can import the local package.
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datamodels.models import (
    TrainingSession,
    Exercise,
    Goal,
    WarmupSet,
    WorkingSet,
    FailureTechnique,
    RepCount,
    RepRange,
    RepQualityAssessment,
)


def test_goal_roundtrip_required_fields():
    d = {"weightKg": 30, "sets": 3, "repRange": {"min": 6, "max": 8}, "restMinutes": 2}
    g = Goal.from_dict(d)
    assert g.weight_kg == 30
    assert g.sets == 3
    assert g.rep_range.min == 6
    assert g.to_dict() == d


def test_warmupset_repcount_optional_none():
    d = {"set": 1, "weightKg": 10}
    w = WarmupSet.from_dict(d)
    assert w.rep_count is None
    # to_dict includes repCount key (None) in this implementation
    out = w.to_dict()
    # serializer omits None repCount
    assert "repCount" not in out


def test_workingset_missing_repcount_raises():
    d = {"set": 1, "weightKg": 20}
    import pytest
    with pytest.raises(Exception):
        WorkingSet.from_dict(d)


def test_rep_quality_enum_case_insensitive_and_serialization():
    d = {
        "set": 1,
        "weightKg": 30,
        "repCount": {"full": 8, "partial": 0},
        "rpe": 8,
        "repQuality": "PeRfeCt",
    }
    ws = WorkingSet.from_dict(d)
    assert isinstance(ws.rep_quality_assessment, RepQualityAssessment)
    assert ws.rep_quality_assessment == RepQualityAssessment.PERFECT
    out = ws.to_dict()
    assert out["repQuality"] == "perfect"


def test_failure_technique_parsing_myo():
    d = {"type": "MyoReps", "details": {"miniSets": [{"miniSet": 1, "repCount": {"full": 3}}]}}
    ft = FailureTechnique.from_dict(d)
    assert ft.technique_type.name == "MYO_REPS"
