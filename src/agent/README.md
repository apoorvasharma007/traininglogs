# agent

## Purpose
Coordinates workout logging domain operations at a high level.

## Main Module
- `workout_agent.py`: prepares sessions, logs exercises, finalizes workout, and provides context/suggestions.

## Boundary
- Uses domain services (`services/*`).
- Does not handle CLI prompt/formatting concerns.
