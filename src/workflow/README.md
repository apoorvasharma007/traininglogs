# workflow

## Purpose
Application workflow control from start/resume through finalize.

## Main Modules
- `session_workflow_service.py`: top-level app workflow.
- `agent_controller_service.py`: turn-level agent control.
- `intent_router_service.py`: deterministic parsed-intent execution.

## Boundary
- Coordinates services and state transitions.
- Actual domain modeling remains in `services/` and `agent/`.
