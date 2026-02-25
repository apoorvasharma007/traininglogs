# state

## Purpose
In-memory runtime state for active session flow.

## Main Module
- `session_state_service.py`: tracks session, draft, and dialogue stage.

## Boundary
- Holds mutable runtime state; no direct persistence writes.
