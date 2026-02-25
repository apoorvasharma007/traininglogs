# data

## Purpose
Persistence orchestration and adapter layer for workflow use.

## Main Modules
- `data_persistence_service.py`: single save/snapshot orchestration entrypoint.
- `cloud_database_repository.py`: optional cloud save adapter.

## Boundary
- Coordinates persistence outcomes.
- Uses concrete persistence implementations directly:
  - local DB repository (`src/persistence/repository.py`)
  - session exporter (`src/persistence/exporter.py`)
  - live session store (`src/persistence/live_session_store.py`)
- Does not contain domain session/exercise logic.
