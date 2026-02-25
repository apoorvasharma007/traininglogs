# traininglogs

Conversational workout logging CLI with strict structured data contracts.

## Project Goal
Build a reliable agentic logger where users type naturally, the app interprets via an LLM layer, and all writes remain deterministic/validated before persistence.

## Current Capabilities
- Start new session or resume in-progress session.
- Conversational metadata intake (`phase`, `week`, `focus`, `is_deload`).
- Conversational exercise logging with draft workflow.
- Warmup sets, working sets, optional exercise fields, undo/commit/finalize.
- Stage-aware follow-up prompts in the main loop.
- Persistence to local SQLite + JSON export + optional cloud Postgres.
- Live event/snapshot files for recovery.

## Runtime Architecture

```text
CLI (src/cli/main.py)
  -> SessionWorkflowService (orchestration)
  -> AgentControllerService (parse/confirm/route per turn)
  -> IntentRouterService (deterministic command execution)
  -> Intake + Validation services
  -> State service (session + draft + dialogue stage)
  -> Data persistence service (db/json/cloud + live snapshot)
```

Design rules:
- LLM interprets intent; router/validators enforce mutation safety.
- Interpreted natural-language actions are previewed and confirmed before apply.
- Schema/datamodel is treated as protected contract.

## Repository Structure

```text
src/
  agent/          Domain orchestration (WorkoutAgent)
  ai/             LLM providers + interpreter boundary
  cli/            Entry point + terminal prompts + command grammar
  config/         Environment/settings
  contracts/      Dataclass contracts between layers
  conversation/   User-facing response/interaction services
  core/           Validation primitives
  data/           Persistence orchestration/adapters
  data_class_model/ Protected data model definitions
  guidance/       History guidance for exercise context
  intake/         Parsing + normalization + intake validation
  persistence/    DB/export/live snapshot implementations
  repository/     Data source abstraction layer
  services/       Session/exercise/history/progression domain services
  state/          In-memory session/draft/dialogue stage state
  workflow/       Session + turn-level workflow controllers

docs/
  architecture.md
  IMPLEMENTATION_PLAN.md
  IMPLEMENTATION_LOG.md
  PHONE_GYM_SETUP.md
```

Each `src/*` component now includes its own `README.md` for high-level design and responsibilities.

## Setup

```bash
cd /Users/apoorvasharma/Projects/traininglogs
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python3 scripts/init_db.py
```

## Run

```bash
python3 -m src.cli.main
```

## Enable LLM Mode (Ollama)

Run Ollama server in a separate terminal:

```bash
ollama serve
```

Then in app terminal:

```bash
export TRAININGLOGS_LLM_ENABLED=true
export TRAININGLOGS_LLM_PROVIDER=ollama
export TRAININGLOGS_OLLAMA_MODEL=qwen2.5:3b-instruct
export TRAININGLOGS_OLLAMA_URL=http://localhost:11434
python3 -m src.cli.main
```

## Testing

Focused suite:

```bash
pytest -q tests/test_agent_controller_service.py tests/test_conversational_ai_service.py tests/test_workflow_services.py tests/test_mobile_cli_components.py
```

Full suite:

```bash
pytest -q
```

Known current issue: full suite still includes existing `data_class_model` compatibility failures in `tests/test_models.py` and `tests/test_validations.py`.

## Persistence Outputs
- SQLite DB: `data/database/traininglogs.db`
- Session JSON exports: `data/output/sessions/`
- Live recovery files: `data/output/live_sessions/`

## Active Docs
- `docs/architecture.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/PHONE_GYM_SETUP.md`

## Guardrails
- Do not modify `src/data_class_model/models.py` without explicit approval.
- If schema blocks required behavior, raise it explicitly before changing model contracts.
