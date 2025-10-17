import sys
import pathlib

# make sure local src package is importable
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datamodels.models import FailureTechnique, FailureTechniqueType, MyoRepDetails, RepCount, TrainingSession, Exercise


def test_failure_technique_aliases():
    aliases = ["myo-reps", "myoreps", "MyoReps", "myo-repcount"]
    for a in aliases:
        ft = FailureTechnique.from_dict({"type": a, "details": {"miniSets": [{"miniSet": 1, "repCount": {"full": 3}}]}})
        assert ft.technique_type == FailureTechniqueType.MYO_REPS


def test_myorepdetails_accepts_int_repcount():
    data = {"miniSets": [{"miniSet": 1, "repCount": 3}, {"miniSet": 2, "repCount": {"full": 2}}]}
    m = MyoRepDetails.from_dict(data)
    assert isinstance(m.mini_sets[0]["repCount"], RepCount)
    assert m.mini_sets[0]["repCount"].full == 3
    assert m.mini_sets[1]["repCount"].full == 2


def test_omit_empty_lists_in_exercise_serialization():
    ex = Exercise(number=1, name="Test", working_sets=[])
    d = ex.to_dict()
    # empty lists should be omitted by serializer
    assert "warmupSets" not in d
    assert "targetMuscleGroups" not in d
    assert "formCues" not in d
