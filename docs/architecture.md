# Architecture

## Purpose
traininglogs is a conversational CLI app for workout logging with strict data contracts.

## High-Level Flow
1. CLI starts and wires dependencies.
2. Session workflow starts new session or resumes snapshot.
3. For each user message:
- Parse intent (`InputParsingService` + optional LLM interpreter).
- Show interpretation/confirmation when needed.
- Route to deterministic intent handler.
- Validate before state mutation.
- Persist live snapshot/events.
4. On `finish`, finalize and persist final session.

## Layered Design

```text
CLI Layer
  src/cli/main.py, prompts.py, mobile_commands.py

Workflow Layer
  src/workflow/session_workflow_service.py
  src/workflow/agent_controller_service.py
  src/workflow/intent_router_service.py

Intake + Validation
  src/intake/*
  src/core/validators.py

State + Domain
  src/state/*
  src/agent/*
  src/services/*

Persistence
  src/data/* (orchestration/adapters)
  src/persistence/* (db/export/live session store)
```

## LLM Boundary
- Single interpretation boundary: `src/ai/llm_interpreter_service.py`
- Provider-specific integrations: `src/ai/llm_provider.py`
- LLM proposes action payloads; deterministic services enforce correctness.

## Data Safety Rules
- No silent mutations from ambiguous text.
- Validation always runs before mutating session/draft state.
- Protected model contract:
  - `src/data_class_model/models.py` changes require explicit approval.

## Persistence Model
- Local DB write is mandatory when user confirms save.
- JSON export is best-effort.
- Cloud write is optional and environment-driven.
- Live recovery files are continuously updated for resume support.
