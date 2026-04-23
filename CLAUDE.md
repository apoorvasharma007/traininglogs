# traininglogs

## What this project is
A Python application for parsing, processing, and storing personal training session logs. Logs are input as markdown/text, parsed into structured Python dataclass models, and serialized to a NoSQL JSON schema.

## Stack
- Language: Python 3
- Models: dataclasses with `to_dict()` / `from_dict()` serialization
- Storage: NoSQL/JSON documents
- Tests: pytest (in `tests/`)
- CLI: `src/cli/`

## Architecture
- `src/core/` — core domain logic
- `src/agent/`, `src/ai/` — AI/agent layer
- `src/data_class_model/` — dataclass models (TrainingSession, Exercise, WorkingSet, etc.)
- `src/contracts/` — schema contracts
- `src/persistence/`, `src/repository/` — storage layer
- `src/workflow/`, `src/services/` — orchestration
- `src/intake/`, `src/conversation/` — input handling
- `data/` — raw and processed data files
- `scripts/` — one-off processing scripts

## Serialization rules
- `to_dict()` uses camelCase JSON keys
- `None` fields and empty lists are omitted (compact serializer)
- `RepQualityAssessment` serialized as lowercase string
- Validation errors raise `TrainingLogValidationError`

## Commands
- Run tests: `pytest tests/`
- Run CLI: `python -m src.cli` (verify before running)

## Working conventions
- Type hints required on all functions
- Follow PEP 8
- Tests required for any new model, parser, or serialization logic
- Do not modify `to_dict()` serialization contracts without explicit instruction — downstream systems depend on key names
