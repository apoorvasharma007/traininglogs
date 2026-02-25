import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai.conversational_ai_service import ConversationalAIService
from ai.llm_interpreter_service import LLMInterpreterService
from data.data_persistence_service import DataPersistenceService
from intake.metadata_service import MetadataService
from intake.input_parsing_service import InputParsingService
from intake.validate_data_service import ValidateDataService
from core.validators import ValidationError


class FakeDbRepo:
    def __init__(self):
        self.saved = []

    def save_session(self, session_id, session_data):
        self.saved.append((session_id, session_data))
        return True


class FakeJsonExporter:
    def __init__(self):
        self.saved = []

    def export_session(self, session_data):
        self.saved.append(session_data)
        return "ok.json"


class FakeLiveStore:
    def __init__(self):
        self.closed = []

    def begin_session(self, session_dict):
        pass

    def append_event(self, session_id, event_type, payload):
        pass

    def update_snapshot(self, session_dict, current_exercise=None):
        pass

    def close_session(self, session_dict, status):
        self.closed.append(status)

    def get_latest_resumable_snapshot(self):
        return None


class FakeCloudRepo:
    mode = "disabled"

    def save_session(self, session_id, session_data):
        return False, None


class FakeProvider:
    enabled = True
    status = "fake"

    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, system_prompt, user_prompt, **kwargs):
        if not self.responses:
            return None
        return self.responses.pop(0)


def test_input_parsing_service_parses_commands_and_metadata(tmp_path):
    ai = LLMInterpreterService(ConversationalAIService(
        FakeProvider(
            [
                '{"updates":{"phase":"phase 3","week":4,"focus":"pull-hypertrophy","is_deload":false},'
                '"preview":"Set phase 3 week 4 pull-hypertrophy no deload","confidence":0.9}'
            ]
        )
    ))
    parser = InputParsingService(
        conversational_ai_service=ai,
    )

    command = parser.parse_workout_input("s 80x5@8", draft_active=True)
    assert command is not None
    assert command.action == "s"
    assert command.argument == "80x5@8"
    assert command.requires_confirmation is False

    metadata = parser.parse_metadata_update(
        "phase 3 week 4 pull hypertrophy no deload",
        {"phase": "phase 2", "week": 1, "focus": "upper-strength", "is_deload": False},
    )
    assert metadata is not None
    updates = metadata.payload["updates"]
    assert updates["phase"] == "phase 3"
    assert updates["week"] == 4
    assert updates["focus"] == "pull-hypertrophy"
    assert updates["is_deload"] is False


def test_input_parsing_service_parses_restart_and_next_phrases(tmp_path):
    parser = InputParsingService()

    restart = parser.parse_workout_input("start over", draft_active=True)
    assert restart is not None
    assert restart.action == "restart"
    assert restart.requires_confirmation is False

    cancel = parser.parse_workout_input("quit program", draft_active=True)
    assert cancel is not None
    assert cancel.action == "cancel"

    nxt = parser.parse_workout_input("go to next exercise cable row", draft_active=True)
    assert nxt is not None
    assert nxt.action == "ex"
    assert nxt.payload["exercise_name"].lower() == "cable row"
    assert nxt.requires_confirmation is True


def test_validate_data_service_rejects_missing_focus():
    validate = ValidateDataService()
    with pytest.raises(ValidationError):
        validate.validate_metadata(
            {
                "phase": "phase 2",
                "week": 5,
                "focus": "",
                "is_deload": False,
            }
        )


def test_data_persistence_service_returns_not_saved_status():
    service = DataPersistenceService(
        database_repository=FakeDbRepo(),
        json_export_service=FakeJsonExporter(),
        live_session_store=FakeLiveStore(),
        cloud_repository=FakeCloudRepo(),
    )
    session = {"id": "abc", "exercises": []}
    outcome = service.persist_final_session("abc", session, save_requested=False)
    assert outcome.status == "not_saved"
    assert outcome.saved_local is False


def test_metadata_service_preview_is_explicit_changes():
    preview = MetadataService._build_update_preview(
        current={"phase": "phase 2", "week": 1, "focus": "upper-strength", "is_deload": False},
        candidate={"phase": "phase 4", "week": 9, "focus": "dance", "is_deload": False},
        updates={"phase": "phase 4", "week": 9, "focus": "dance"},
    )
    assert "phase: phase 4" in preview
    assert "week: 9" in preview
    assert "focus: dance" in preview
    assert "->" not in preview
