import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from repository.hybrid_data_source import HybridDataSource
from services.session_service import SessionService, SessionMetadata


class FakeRepo:
    def __init__(self, sessions):
        self._sessions = sessions

    def get_all_sessions(self):
        return self._sessions

    def save_session(self, session_id, session_data):
        return True


def test_hybrid_data_source_returns_latest_exercise_deterministically(tmp_path):
    repo = FakeRepo(
        [
            {
                "id": "old-1",
                "date": "2026-02-10T10:00:00",
                "exercises": [{"name": "Bench Press", "working_sets": [{"weight": 80, "reps": 5}]}],
            },
            {
                "id": "new-1",
                "date": "2026-02-12T10:00:00",
                "exercises": [{"name": "Bench Press", "working_sets": [{"weight": 90, "reps": 5}]}],
            },
        ]
    )
    ds = HybridDataSource(repo, json_dir=str(tmp_path))

    last = ds.get_last_exercise("Bench Press")

    assert last is not None
    assert last["working_sets"][0]["weight"] == 90
    assert last["session_date"] == "2026-02-12T10:00:00"


def test_hybrid_data_source_normalizes_schema_style_json(tmp_path):
    session = {
        "_id": "schema-1",
        "date": "2026-02-11T08:00:00",
        "phase": 2,
        "week": 7,
        "focus": "upper-strength",
        "isDeloadWeek": False,
        "exercises": [
            {
                "Name": "Incline Press",
                "warmupSets": [{"weightKg": 20, "repCount": 8}],
                "workingSets": [{"weightKg": 40, "repCount": {"full": 6, "partial": 1}, "rpe": 8}],
            }
        ],
    }
    file_path = tmp_path / "session.json"
    file_path.write_text(json.dumps(session))

    ds = HybridDataSource(FakeRepo([]), json_dir=str(tmp_path))
    history = ds.get_exercise_history("Incline Press", limit=1)

    assert len(history) == 1
    ex = history[0]
    assert ex["name"] == "Incline Press"
    assert ex["warmup_sets"][0]["weight"] == 20
    assert ex["warmup_sets"][0]["reps"] == 8
    assert ex["working_sets"][0]["weight"] == 40
    assert ex["working_sets"][0]["reps"] == 7
    assert ex["working_sets"][0]["rpe"] == 8


def test_session_service_is_stateless_and_sets_default_date():
    service = SessionService()
    meta = SessionMetadata(
        phase="phase 2",
        week=3,
        focus="pull-hypertrophy",
        is_deload=False,
        date=None,
    )

    session = service.create_session(meta)

    assert session.metadata.date is not None
    assert isinstance(session.metadata.date, str)
    assert session.exercises == []
