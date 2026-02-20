# Conversational CLI Workout Agent Architecture

This document describes the phone-friendly CLI POC in simple language.

## 1) System View

```mermaid
flowchart TD
    U[iPhone Terminal App] --> S[SSH or Tailscale Tunnel]
    S --> C[traininglogs CLI]
    C --> A[WorkoutAgent]
    A --> HS[HistoryService]
    A --> PS[ProgressionService]
    A --> ES[ExerciseService]
    A --> SS[SessionService]
    HS --> DS[HybridDataSource]
    DS --> DB[(SQLite)]
    C --> EXP[SessionExporter]
    C --> LIVE[LiveSessionStore]
    EXP --> JSON[(Session JSON Files)]
    LIVE --> EV[(Event Log JSONL)]
    LIVE --> SNAP[(Live Snapshot JSON)]
```

## 2) Runtime Components

```mermaid
flowchart LR
    subgraph CLI Layer
      MAIN[src/cli/main.py]
      PROMPTS[src/cli/prompts.py]
      CMDS[src/cli/mobile_commands.py]
      NLU[src/cli/nlu_interpreter.py]
    end

    subgraph Agent Layer
      AGENT[src/agent/workout_agent.py]
    end

    subgraph Service Layer
      H[src/services/history_service.py]
      P[src/services/progression_service.py]
      E[src/services/exercise_service.py]
      SE[src/services/session_service.py]
    end

    subgraph Data Layer
      HD[src/repository/hybrid_data_source.py]
      REPO[src/persistence/repository.py]
      LIVE[src/persistence/live_session_store.py]
      EXP2[src/persistence/exporter.py]
      DB2[(traininglogs.db)]
      OUT[(data/output)]
    end

    MAIN --> PROMPTS
    MAIN --> CMDS
    MAIN --> NLU
    MAIN --> AGENT
    AGENT --> H
    AGENT --> P
    AGENT --> E
    AGENT --> SE
    H --> HD
    HD --> REPO
    REPO --> DB2
    MAIN --> LIVE
    MAIN --> EXP2
    LIVE --> OUT
    EXP2 --> OUT
```

## 3) Conversational Loop

```mermaid
sequenceDiagram
    participant User as User (Phone)
    participant CLI as CLI Main
    participant Agent as WorkoutAgent
    participant Live as LiveSessionStore
    participant DB as Persistence

    User->>CLI: ex Bench Press
    CLI->>Agent: prepare_exercise_logging("Bench Press")
    Agent-->>CLI: history + suggestions
    CLI->>Live: append_event(exercise_started)
    CLI->>Live: update_snapshot

    User->>CLI: w 40x5
    CLI->>Live: append_event(set_added warmup)
    CLI->>Live: update_snapshot

    User->>CLI: s 80x5@8
    CLI->>Live: append_event(set_added working)
    CLI->>Live: update_snapshot

    User->>CLI: done
    CLI->>Agent: log_exercise(session, draft)
    Agent-->>CLI: success
    CLI->>Live: append_event(exercise_committed)
    CLI->>Live: update_snapshot

    User->>CLI: finish
    CLI->>Agent: finalize_workout(session)
    CLI->>DB: save session
    CLI->>Live: close_session(saved)
```

## 4) Command Grammar

```mermaid
flowchart TD
    IN[User Input] --> PARSE[parse_command]
    PARSE --> NORM[normalize_command]
    NORM --> EX{Command Type}
    EX -->|ex| DRAFT[Start Draft Exercise]
    EX -->|w or s| SET[parse_set_notation + add set]
    EX -->|done| COMMIT[Commit draft via agent]
    EX -->|undo| UNDO[Remove last set]
    EX -->|status| STATUS[Show quick state]
    EX -->|finish| FINALIZE[Finalize + save]
    EX -->|cancel| CANCEL[Cancel session]
    EX -->|help| HELP[Show command help]
```

## 5) Autosave Model

```mermaid
flowchart LR
    EVT[Every action] --> APPEND[Append event JSON line]
    EVT --> SNAP[Rewrite snapshot JSON]
    APPEND --> EFILE[session_id.events.jsonl]
    SNAP --> SFILE[session_id.snapshot.json]
```

The event log is append-only for audit.  
The snapshot is the latest recoverable state.

## 6) Resume + Learning

```mermaid
flowchart TD
    START[App Start] --> CHECK[Check latest resumable snapshot]
    CHECK -->|found| ASK[Ask user to resume]
    ASK -->|yes| RESTORE[Restore Session + Draft]
    ASK -->|no| NEW[Create New Session]
    CHECK -->|none| NEW

    INPUT[User free-text input] --> PARSE[NLU Interpreter]
    PARSE --> PREVIEW[Show interpreted action]
    PREVIEW --> CONFIRM{User confirms?}
    CONFIRM -->|yes| APPLY[Apply action]
    APPLY --> LEARN[Remember phrase mapping]
    CONFIRM -->|no| RETRY[Ask user to rephrase]
```
