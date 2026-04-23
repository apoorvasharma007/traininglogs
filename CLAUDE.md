# traininglogs

## What this project is
A Python CLI for parsing personal training session logs from markdown into structured JSON. Input is hand-written markdown logs; output is a camelCase JSON document per session.

## Stack
- Python 3.10+
- Dataclass models with `to_dict()` / `from_dict()` serialisation
- Output: JSON files on disk
- Tests: pytest
- CLI: `traininglogs` entry point (installed via `pip install -e .`)

## Project layout
```
src/traininglogs/
  models/      — dataclass models (TrainingSession, Exercise, WorkingSet, etc.)
  parser/      — extract.py (markdown → intermediate dict), parse.py (dict → objects)
  processor/   — processor.py (CLI entry point, file I/O)
scripts/
  process_and_commit.py  — end-to-end workflow: parse → commit → optional PR
tests/
  test_models.py         — model serialisation roundtrip tests
  test_validations.py    — model validation and edge case tests
input_training_logs_md/  — input markdown logs, organised as "phase X week Y/"
output_training_logs_json/ — output JSON, organised as "<program>/phase X/week Y/"
```

## Serialisation rules
- `to_dict()` uses camelCase JSON keys
- `None` fields and empty lists are omitted
- `RepQualityAssessment` serialised as lowercase string
- Validation errors raise `TrainingLogValidationError`

## Commands
```bash
# Install (once)
pip install -e .

# Parse logs for a phase/week
traininglogs --phase 3 --week 5

# Full workflow (parse + commit + optional PR)
python scripts/process_and_commit.py --phase 3 --week 5 [--pr]

# Run tests
pytest tests/
```

## Working conventions
- Type hints required on all functions
- Follow PEP 8
- Tests required for any new model, parser, or serialisation logic
- Do not change `to_dict()` key names without explicit instruction — downstream JSON depends on them
