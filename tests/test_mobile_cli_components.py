import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cli.mobile_commands import parse_command, normalize_command, parse_set_notation
from cli.prompts import _parse_yes_no
from persistence.live_session_store import LiveSessionStore


def test_parse_command_and_aliases():
    cmd, arg = parse_command("ex Bench Press")
    assert cmd == "ex"
    assert arg == "Bench Press"
    assert normalize_command("st") == "status"
    assert normalize_command("?") == "help"
    assert normalize_command("/restart") == "restart"
    assert normalize_command("/quit") == "cancel"


def test_parse_set_notation_accepts_expected_formats():
    assert parse_set_notation("80x5") == {"weight": 80.0, "reps": 5}
    assert parse_set_notation("82.5x6@8") == {"weight": 82.5, "reps": 6, "rpe": 8.0}
    assert parse_set_notation("82.5 x 6 @ 8") == {"weight": 82.5, "reps": 6, "rpe": 8.0}
    assert parse_set_notation("bad-format") is None


def test_parse_yes_no_accepts_common_words():
    assert _parse_yes_no("y") is True
    assert _parse_yes_no("yes") is True
    assert _parse_yes_no("n") is False
    assert _parse_yes_no("no") is False
    assert _parse_yes_no("maybe") is None


def test_live_session_store_writes_event_and_snapshot(tmp_path):
    store = LiveSessionStore(str(tmp_path))
    session = {
        "id": "session-123",
        "date": "2026-02-18T10:00:00",
        "phase": "phase 2",
        "week": 7,
        "focus": "upper-strength",
        "is_deload": False,
        "exercises": [],
        "created_at": "2026-02-18T10:00:00",
    }
    draft = {"name": "Bench Press", "warmup_sets": [], "working_sets": [], "notes": None}

    store.begin_session(session)
    store.append_event(session["id"], "exercise_started", {"exercise_name": "Bench Press"})
    store.update_snapshot(session, current_exercise=draft)
    store.close_session(session, status="saved")

    events_path = tmp_path / "session-123.events.jsonl"
    snapshot_path = tmp_path / "session-123.snapshot.json"

    assert events_path.exists()
    assert snapshot_path.exists()

    lines = events_path.read_text().strip().splitlines()
    assert len(lines) >= 3

    snapshot = json.loads(snapshot_path.read_text())
    assert snapshot["session"]["id"] == "session-123"
    assert snapshot["status"] == "saved"


def test_live_session_store_latest_resumable_snapshot(tmp_path):
    store = LiveSessionStore(str(tmp_path))

    s1 = {
        "id": "session-old",
        "date": "2026-02-18T09:00:00",
        "phase": "phase 2",
        "week": 7,
        "focus": "upper-strength",
        "is_deload": False,
        "exercises": [],
        "created_at": "2026-02-18T09:00:00",
    }
    s2 = {
        "id": "session-new",
        "date": "2026-02-18T10:00:00",
        "phase": "phase 2",
        "week": 7,
        "focus": "upper-strength",
        "is_deload": False,
        "exercises": [],
        "created_at": "2026-02-18T10:00:00",
    }

    store.begin_session(s1)
    store.close_session(s1, status="saved")
    store.begin_session(s2)

    latest = store.get_latest_resumable_snapshot()
    assert latest is not None
    assert latest["session"]["id"] == "session-new"
    assert latest["status"] == "in_progress"
