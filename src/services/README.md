# services

## Purpose
Core domain services used by agent/workflow layers.

## Main Modules
- `session_service.py`: session object lifecycle.
- `exercise_service.py`: exercise object creation/validation.
- `history_service.py`: historical exercise retrieval.
- `progression_service.py`: progression suggestions.

## Boundary
- Domain logic without CLI-specific coupling.
