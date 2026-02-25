# conversation

## Purpose
User-facing conversation behavior and response rendering.

## Main Modules
- `user_conversation_service.py`: interaction loop helpers.
- `conversation_response_service.py`: status/summary/persistence text rendering.

## Boundary
- Controls how information is presented.
- Does not own domain validation or persistence.
