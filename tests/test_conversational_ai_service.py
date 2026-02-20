import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai.conversational_ai_service import ConversationalAIService
from ai.llm_interpreter_service import LLMInterpreterService
from intake.input_parsing_service import InputParsingService


class FakeProvider:
    enabled = True
    status = "fake"

    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, system_prompt, user_prompt, **kwargs):
        if not self.responses:
            return None
        return self.responses.pop(0)


def test_ai_service_parses_workout_action():
    provider = FakeProvider(
        [
            '{"action":"s","payload":{"set_data":{"weight":82.5,"reps":6,"rpe":8}},'
            '"preview":"Add working set 82.5x6 @8","confidence":0.88}'
        ]
    )
    ai = ConversationalAIService(provider)
    result = ai.parse_workout_action("did 82.5 for 6 at 8", draft_active=True)
    assert result is not None
    assert result["action"] == "s"
    assert result["payload"]["set_data"]["weight"] == 82.5
    assert result["payload"]["set_data"]["reps"] == 6


def test_ai_service_parses_restart_action():
    provider = FakeProvider(
        [
            '{"action":"restart","payload":{},'
            '"preview":"Restart session from fresh setup","confidence":0.93}'
        ]
    )
    ai = ConversationalAIService(provider)
    result = ai.parse_workout_action("restart this session", draft_active=True)
    assert result is not None
    assert result["action"] == "restart"
    assert result["payload"] == {}


def test_ai_service_parses_metadata_update():
    provider = FakeProvider(
        [
            '{"updates":{"phase":"phase 3","week":5,"focus":"pull-hypertrophy","is_deload":false},'
            '"preview":"Set phase 3 week 5 pull-hypertrophy, no deload",'
            '"confidence":0.9}'
        ]
    )
    ai = ConversationalAIService(provider)
    result = ai.parse_metadata_update(
        "phase 3 week 5 pull hypertrophy no deload",
        {"phase": "phase 2", "week": 1, "focus": "upper-strength", "is_deload": False},
    )
    assert result is not None
    updates = result["payload"]["updates"]
    assert updates["phase"] == "phase 3"
    assert updates["week"] == 5
    assert updates["focus"] == "pull-hypertrophy"
    assert updates["is_deload"] is False


def test_ai_service_metadata_focus_synonym_normalization():
    provider = FakeProvider(
        [
            '{"updates":{"phase":"phase 9","week":7,"focus":"yoga","is_deload":false},'
            '"preview":"Set metadata for phase 9 week 7 yoga",'
            '"confidence":0.92}'
        ]
    )
    ai = ConversationalAIService(provider)
    result = ai.parse_metadata_update(
        "phase 9 week 7 focus yoga",
        {"phase": "phase 2", "week": 1, "focus": "upper-strength", "is_deload": False},
    )
    assert result is not None
    updates = result["payload"]["updates"]
    assert updates["phase"] == "phase 9"
    assert updates["week"] == 7
    assert updates["focus"] == "mobility"


def test_input_parsing_service_uses_ai_when_enabled(tmp_path):
    provider = FakeProvider(
        [
            '{"action":"ex","payload":{"exercise_name":"Incline Dumbbell Press"},'
            '"preview":"Start exercise Incline Dumbbell Press","confidence":0.86}'
        ]
    )
    ai = LLMInterpreterService(ConversationalAIService(provider))
    parser = InputParsingService(
        str(tmp_path / "nlu_learning.json"),
        conversational_ai_service=ai,
    )

    parsed = parser.parse_workout_input("let us do incline dumbbell press", draft_active=False)
    assert parsed is not None
    assert parsed.source == "llm"
    assert parsed.action == "ex"
    assert parsed.payload["exercise_name"] == "Incline Dumbbell Press"


def test_ai_service_preview_null_uses_fallback_text():
    provider = FakeProvider(
        [
            '{"updates":{"phase":"phase 4","week":2,"focus":"upper-strength","is_deload":false},'
            '"preview":null,"confidence":0.91}'
        ]
    )
    ai = ConversationalAIService(provider)
    result = ai.parse_metadata_update(
        "phase 4 week 2 upper strength no deload",
        {"phase": "phase 2", "week": 1, "focus": "upper-strength", "is_deload": False},
    )
    assert result is not None
    assert result["preview"] == "Update session metadata."
