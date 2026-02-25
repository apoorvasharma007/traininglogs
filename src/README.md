# Source Layout

This folder contains the application runtime in layered modules.

## Top-Level Components
- `agent/`: domain-level workout orchestration.
- `ai/`: LLM providers and interpretation boundary.
- `cli/`: terminal entrypoint, prompt I/O, command grammar.
- `config/`: environment/settings.
- `contracts/`: shared dataclass contracts.
- `conversation/`: user-facing response/interaction services.
- `core/`: low-level validators.
- `data/`: persistence orchestration and adapters.
- `data_class_model/`: protected core model definitions.
- `guidance/`: history-based exercise guidance.
- `intake/`: parsing, intake normalization, validation.
- `persistence/`: DB, migration, export, live snapshot implementation.
- `repository/`: data source abstraction.
- `services/`: core domain services (session/exercise/history/progression).
- `state/`: in-memory session/draft/dialogue state.
- `workflow/`: session and turn-level workflow control.

Each subfolder includes its own `README.md` with high-level responsibilities.
