# persistence

## Purpose
Concrete persistence implementations.

## Main Modules
- `database.py`: DB connection/schema bootstrap.
- `repository.py`: training session DB repository.
- `migrations.py`: schema version checks.
- `exporter.py`: session JSON exporter.
- `live_session_store.py`: event/snapshot autosave store.

## Boundary
- Low-level persistence implementation details.
