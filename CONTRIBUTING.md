# Contributing

## Principles
- Keep behavior deterministic where data mutates.
- Keep modules small, focused, and SOLID-aligned.
- Respect protected datamodel files.

## Protected Files
- `src/data_class_model/models.py` must not be changed without explicit approval.

## Development Flow
1. Implement scoped change.
2. Run focused test suite.
3. Smoke-run CLI.
4. Update docs if behavior/architecture changed.

## Setup

```bash
cd /Users/apoorvasharma/Projects/traininglogs
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python3 scripts/init_db.py
```

## Run + Test

```bash
# run app
python3 -m src.cli.main

# focused tests
pytest -q tests/test_agent_controller_service.py tests/test_conversational_ai_service.py tests/test_workflow_services.py tests/test_mobile_cli_components.py

# full tests
pytest -q
```

## LLM Mode (Ollama)

```bash
export TRAININGLOGS_LLM_ENABLED=true
export TRAININGLOGS_LLM_PROVIDER=ollama
export TRAININGLOGS_OLLAMA_MODEL=qwen2.5:3b-instruct
export TRAININGLOGS_OLLAMA_URL=http://localhost:11434
python3 -m src.cli.main
```

## Documentation Rules
- Root `README.md` is the single project overview source.
- Component-level docs live in `src/*/README.md`.
- Planning/progress docs live in `docs/`.
