import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from intake.input_parsing_service import ParsedAction
from state.session_state_service import SessionStateService
from workflow.agent_controller_service import AgentControllerService
from workflow.intent_router_service import RouteResult


class FakeConversation:
    def __init__(self, confirm_response=True):
        self.confirm_response = confirm_response
        self.infos = []
        self.errors = []
        self.confirm_prompts = []

    def show_info(self, message):
        self.infos.append(message)

    def show_error(self, message):
        self.errors.append(message)

    def confirm_action(self, question):
        self.confirm_prompts.append(question)
        return self.confirm_response


class FakeParser:
    def __init__(self, parsed=None, ai_enabled=True):
        self.parsed = parsed
        self.ai_enabled = ai_enabled
        self.remembered = []

    def parse_workout_input(self, raw, draft_active):
        return self.parsed

    def remember_interpretation(self, raw, parsed):
        self.remembered.append((raw, parsed.action))

    def is_ai_enabled(self):
        return self.ai_enabled


class FakeState:
    def __init__(self, draft=None, stage="awaiting_exercise"):
        self._draft = draft
        self._stage = stage

    def get_draft(self):
        return self._draft

    def set_draft(self, draft):
        self._draft = draft

    def get_dialogue_stage(self):
        return self._stage

    def set_dialogue_stage(self, stage):
        self._stage = stage


class FakeRouter:
    def __init__(self, state, route_result=None, on_route=None):
        self.state = state
        self.route_result = route_result or RouteResult("continue")
        self.on_route = on_route
        self.calls = []

    def route(self, parsed, restart_exit_code):
        self.calls.append((parsed.action, restart_exit_code))
        if self.on_route:
            self.on_route(self.state, parsed)
        return self.route_result


def test_agent_controller_prompts_for_first_set_after_ex():
    state = FakeState()
    parser = FakeParser(
        ParsedAction(action="ex", payload={"exercise_name": "Gymnastic Ring Dips"})
    )

    def _on_route(local_state, parsed):
        local_state.set_draft({"name": parsed.payload["exercise_name"], "warmup_sets": [], "working_sets": []})
        local_state.set_dialogue_stage("exercise_selected")

    router = FakeRouter(state, route_result=RouteResult("continue", prompt_next=True), on_route=_on_route)
    conversation = FakeConversation()
    controller = AgentControllerService(conversation, parser, state, router)

    result = controller.handle_user_turn("start with gymnastic ring dips", restart_exit_code=90)
    assert result.outcome == "continue"
    assert any("first set" in line.lower() for line in conversation.infos)


def test_agent_controller_handles_yes_without_pending_confirmation():
    state = FakeState(draft=None, stage="awaiting_exercise")
    parser = FakeParser(parsed=None, ai_enabled=True)
    router = FakeRouter(state)
    conversation = FakeConversation()
    controller = AgentControllerService(conversation, parser, state, router)

    result = controller.handle_user_turn("y", restart_exit_code=90)
    assert result.outcome == "continue"
    assert conversation.errors == []
    assert any("no confirmation is pending" in line.lower() for line in conversation.infos)


def test_agent_controller_prompts_after_done_action():
    state = FakeState(draft=None, stage="awaiting_exercise")
    parser = FakeParser(ParsedAction(action="done"))
    router = FakeRouter(state, route_result=RouteResult("continue", prompt_next=True))
    conversation = FakeConversation()
    controller = AgentControllerService(conversation, parser, state, router)

    result = controller.handle_user_turn("done", restart_exit_code=90)
    assert result.outcome == "continue"
    assert any("exercise saved" in line.lower() for line in conversation.infos)


def test_session_state_service_syncs_dialogue_stage_with_draft():
    state = SessionStateService()
    assert state.get_dialogue_stage() == SessionStateService.STAGE_IDLE

    state.set_draft({"name": "Flywheel", "warmup_sets": [], "working_sets": []})
    assert state.get_dialogue_stage() == SessionStateService.STAGE_EXERCISE_SELECTED

    state.set_draft({"name": "Flywheel", "warmup_sets": [{"weight": 0, "reps": 10}], "working_sets": []})
    assert state.get_dialogue_stage() == SessionStateService.STAGE_WARMUP_LOGGING

    state.set_draft(
        {
            "name": "Flywheel",
            "warmup_sets": [{"weight": 0, "reps": 10}],
            "working_sets": [{"weight": 20, "reps": 8}],
        }
    )
    assert state.get_dialogue_stage() == SessionStateService.STAGE_WORKING_LOGGING

    state.clear_draft()
    assert state.get_dialogue_stage() == SessionStateService.STAGE_IDLE
