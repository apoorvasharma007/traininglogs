# Implementation Plan

## Objective
Build a robust conversational workout logger where users type naturally and the app maps input to strict backend structures with deterministic validation and persistence.

## Non-Negotiable Guardrails
1. **Datamodel protection**
- Do not edit `src/data_class_model/models.py` without explicit approval.
- If functionality is blocked by schema, raise a concrete schema-gap note first.

2. **Deterministic mutation path**
- LLM proposes intent.
- Router + validators own state mutation decisions.

3. **No silent writes**
- Interpreted natural-language actions are previewed/confirmed before apply.

## Current Runtime Architecture
- `src/cli/main.py`: bootstrap/dependency wiring.
- `src/workflow/session_workflow_service.py`: session-level flow.
- `src/workflow/agent_controller_service.py`: turn-level interpret/confirm/route policy.
- `src/workflow/intent_router_service.py`: deterministic intent execution.
- `src/intake/*` + `src/core/validators.py`: parsing + validation.
- `src/state/session_state_service.py`: session/draft/dialogue stage state.
- `src/data/data_persistence_service.py`: persistence orchestration.

## Documentation Standard
- Root `README.md`: complete project overview and run/test instructions.
- `docs/`: architecture + implementation plan/log + operations references.
- `src/*/README.md`: concise high-level component design/functionality.

## Active Work Phases

### Phase A: Conversation Reliability
Goal: reliable basic conversational logging without command fallbacks.

Backlog:
- Improve parsing for conversational set plans.
- Reduce “I couldn't parse” dead-ends.
- Preserve clear confirmation UX.

### Phase B: Agent Prompt Policy
Goal: context-aware follow-up prompts that move user to next correct step.

Backlog:
- Expand clarification policy for ambiguous intent.
- Keep prompt style concise and consistent.

### Phase C: Optional Field Completeness
Goal: optional exercise/session fields can be captured naturally at any point.

Backlog:
- Improve parsing/validation for optional metadata fields.
- Add tests for optional-field resume/restore paths.

### Phase D: Quality Harness
Goal: measurable conversational quality across real transcripts.

Backlog:
- Add transcript-driven regression tests.
- Add intent routing metrics and audit events.

## Testing Strategy
- Fast suite (workflow-focused):
  - `tests/test_agent_controller_service.py`
  - `tests/test_conversational_ai_service.py`
  - `tests/test_workflow_services.py`
  - `tests/test_mobile_cli_components.py`
- Full suite:
  - `pytest -q` (currently has known existing `data_class_model` compatibility failures).

## Daily Resume Protocol
1. Open `docs/IMPLEMENTATION_LOG.md`.
2. Continue from latest “Next Session Start” list.
3. Run fast suite before and after edits.
4. Update log with:
- changed files
- behavior changes
- tests run
- open risks
