# TrainingLogs Architecture Redesign

## Overview

Complete architectural redesign moving from monolithic CLI orchestration to a service-based, agent-driven system. This document describes the new architecture, rationale, and implementation details.

---

## Architecture Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI (Thin I/O Layer)                     │
│  • User prompts for metadata, exercise names, sets          │
│  • Shows context and suggestions to user                    │
│  • No business logic (delegates to agent)                   │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────▼────────────────┐
         │     WorkoutAgent (Orchestrator) │
         │   (Intelligent Decision Making) │
         └───────────────┬────────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    ┌─────▼─────┐  ┌────▼────┐  ┌─────▼──────┐
    │  Services │  │ Services│  │  Services  │
    ├───────────┤  ├─────────┤  ├────────────┤
    │ History   │  │Progress │  │ Exercise   │
    │ Service   │  │ Service │  │  Service   │
    └─────┬─────┘  └────┬────┘  └─────┬──────┘
          │             │             │
          └─────────────┼─────────────┘
                        │
          ┌─────────────▼──────────────┐
          │   DataSource (Abstraction)  │
          │  (Queries DB or JSON)      │
          └─────────────┬──────────────┘
                        │
          ┌─────────────▼──────────────┐
          │  Persistence Layer         │
          │  • SQLite Database         │
          │  • JSON Files              │
          └────────────────────────────┘
```

### Key Principle: Separation of Concerns

- **CLI**: Only I/O and user interaction
- **Agent**: Orchestration and high-level decisions
- **Services**: Pure business logic (no side effects, no UI)
- **DataSource**: Abstract data access (swappable storage)
- **Persistence**: Implementation details (SQLite, JSON)

---

## Core Components

### 1. Data Access Layer (`src/repository/`)

#### `data_source.py` - Abstract Interface
```python
class DataSource:
    """Abstract interface for data queries."""
    
    def get_last_exercise(self, exercise_name: str) -> Optional[ExerciseOccurrence]
    def get_exercise_history(self, exercise_name: str, limit: int = 10) -> list
    def get_sessions(self, phase: str, week: int) -> list
    def save_session(self, session_dict: dict) -> bool
    def get_session(self, session_id: str) -> Optional[dict]
    def search_exercises(self, query: str) -> list
```

**Purpose:** Services never query the database directly. They ask DataSource, which can fetch from:
- SQLite database (primary)
- JSON files (fallback)
- API (future implementation)

#### `hybrid_data_source.py` - Dual Storage
```python
class HybridDataSource(DataSource):
    """Queries database first, falls back to JSON files."""
    
    # Queries SQLite first (faster)
    # Falls back to JSON files if not found
    # Normalizes results to look identical regardless of source
```

**Benefits:**
- Works with existing SQLite database
- Can fallback to JSON files
- Easy to test (mock DataSource)
- Easy to migrate storage later

---

### 2. Services Layer (`src/services/`)

Pure business logic - **zero UI coupling**, **zero persistence coupling**.

#### `history_service.py` - Exercise History Queries

```python
class ExerciseOccurrence:
    """Exercise with temporal context."""
    exercise: Exercise
    days_ago: int
    session_date: datetime

class HistoryService:
    def get_last_exercise(self, exercise_name: str) -> Optional[ExerciseOccurrence]
    def get_exercise_progression(self, exercise_name: str) -> list[ExerciseOccurrence]
    def get_max_weight_achieved(self, exercise_name: str) -> Optional[float]
    def get_typical_weight_range(self, exercise_name: str) -> tuple[float, float]
    def get_typical_rpe_range(self, exercise_name: str) -> tuple[int, int]
    def is_new_exercise(self, exercise_name: str) -> bool
    def days_since_last_attempt(self, exercise_name: str) -> Optional[int]
```

**Used by:** ProgressionService (for suggestions), Agent (for context)

#### `progression_service.py` - Weight/Rep Suggestions

```python
class ProgressionSuggestion:
    weight: float
    reasoning: str  # Why this weight?
    confidence: int  # 1-10
    alternatives: list[float]

class ProgressionService:
    def suggest_next_weight(self, exercise_name: str) -> Optional[ProgressionSuggestion]
        # Smart heuristics:
        # - If reps increased last time → increase weight
        # - If RPE < 8 → increase weight
        # - If below max ever → encourage max
        # - Else: standard progression (+2.5kg upper body, +5kg lower body)
    
    def suggest_rep_range(self, exercise_name: str) -> tuple[int, int]
    def suggest_warmups(self, working_weight: float) -> list[dict]
    def get_volume_trend(self, exercise_name: str) -> dict
```

**Used by:** Agent (for smart prompting), CLI (to show suggestions)

#### `exercise_service.py` - Exercise Building

```python
class Exercise:
    name: str
    warmup_sets: list[dict]  # {weight, reps, [rpe]}
    working_sets: list[dict]
    notes: Optional[str]

class ExerciseService:
    def build_exercise(self, name: str, warmup_sets: list, working_sets: list) -> Exercise
        # Validates all inputs
        # No side effects, pure function
        
    def validate_exercise(self, exercise: Exercise) -> tuple[bool, Optional[str]]
    def get_exercise_summary(self, exercise: Exercise) -> dict
    def estimate_rpe(self, weight: float, reps: int, exercise_name: str) -> int
```

**Key Point:** Completely programmatic (no prompts). Can be used by:
- CLI (user input)
- API (external requests)
- Batch processing (migrations)

#### `session_service.py` - Session Lifecycle

```python
class SessionMetadata:
    phase: str
    week: int
    focus: str  # upper-strength, pull-hypertrophy, etc.
    is_deload: bool
    date: datetime

class Session:
    id: str
    metadata: SessionMetadata
    exercises: list[Exercise]
    created_at: datetime

class SessionService:
    def create_session(self, metadata_dict: dict) -> Session
    def add_exercise(self, session: Session, exercise: Exercise) -> bool
    def finalize_session(self, session: Session) -> bool
    def get_session_summary(self, session: Session) -> dict
```

**Purpose:** Session state management. No persistence, no validation.

---

### 3. Orchestration Layer (`src/agent/`)

#### `workout_agent.py` - Intelligent Coordinator

```python
class LoggingContext:
    """Context for smart prompting."""
    exercise_name: str
    is_new_exercise: bool
    last_weight: Optional[float]
    last_reps: Optional[int]
    last_rpe: Optional[int]
    max_weight: Optional[float]
    suggested_weight: Optional[float]
    suggested_reps_range: Optional[tuple[int, int]]
    days_since_last: Optional[int]

class LoggingError:
    """Error with recovery suggestions."""
    error_type: str
    message: str
    suggestions: list[str]  # User-friendly hints

class WorkoutAgent:
    """Orchestrates entire workout logging workflow."""
    
    def prepare_workout_session(self, phase: str, week: int, focus: str, is_deload: bool) -> Session
        # Creates session via SessionService
        
    def prepare_exercise_logging(self, exercise_name: str) -> LoggingContext
        # Queries history via HistoryService
        # Gets suggestions via ProgressionService
        # Returns rich context for smart prompting
        
    def log_exercise(self, session: Session, name: str, warmup_sets: list, working_sets: list) -> (bool, Optional[LoggingError])
        # Builds exercise via ExerciseService
        # Validates via ExerciseService
        # Adds to session via SessionService
        # Returns success or detailed error with hints
        
    def finalize_workout(self, session: Session) -> (bool, Optional[LoggingError])
        # Ensures session is valid
        # Ready for persistence
        
    def get_next_exercise_suggestions(self, session: Session) -> list[str]
    def get_error_recovery_hints(self, error: LoggingError) -> str
```

**Single Responsibility:** Coordinate all services to implement the complete workflow. No business logic duplication.

---

### 4. Refactored CLI (`src/cli/main.py`)

```python
# === THIN I/O LAYER ===

def main():
    # Initialize (not business logic)
    db = get_database(settings.get_db_path())
    data_source = HybridDataSource(...)
    
    # Create services
    history_service = HistoryService(data_source)
    progression_service = ProgressionService(history_service)
    exercise_service = ExerciseService()
    session_service = SessionService()
    
    # Create agent - THE BRAIN
    agent = WorkoutAgent(...)
    
    # Get metadata from user
    metadata = prompts.prompt_session_metadata()
    
    # Agent creates session
    session = agent.prepare_workout_session(metadata...)
    
    # Exercise loop
    while True:
        exercise_name = prompts.prompt_exercise_name(...)
        
        # Agent prepares context (queries history, suggests progression)
        context = agent.prepare_exercise_logging(exercise_name)
        
        # Show context to user (SMART PROMPTING!)
        prompts.show_exercise_context(context)
        
        # Get sets from user
        warmup_sets = prompts.prompt_sets("warmup", 
            suggested_count=2,
            suggested_weight=context.suggested_weight)
        working_sets = prompts.prompt_sets("working",
            suggested_count=1,
            suggested_weight=context.suggested_weight,
            suggested_reps_range=context.suggested_reps_range)
        
        # Agent validates and adds
        success, error = agent.log_exercise(session, exercise_name, warmup_sets, working_sets)
        
        if not success:
            hint = agent.get_error_recovery_hints(error)
            prompts.show_error(hint)
        
    # Agent finalizes
    success, error = agent.finalize_workout(session)
    
    # Save to persistence
    db_repo.save_session(session.id, session.to_dict())
    exporter.export_session(session.to_dict())
```

**Key Changes:**
- Removed SessionManager (agent replaces it)
- Removed ExerciseBuilder and its UI coupling
- Removed ad-hoc business logic
- Agent provides all intelligence
- CLI is 100% I/O focused

---

### 5. CLI Prompts Updates (`src/cli/prompts.py`)

**New Functions:**

```python
def show_exercise_context(context: LoggingContext):
    """Display exercise history and suggestions."""
    # Shows:
    # - Is new exercise?
    # - Last weight (days ago)
    # - Max weight achieved
    # - Suggested weight
    # - Suggested reps range

def prompt_sets(set_type: str, suggested_count: int = 1, 
                suggested_weight: float = None,
                suggested_reps_range: tuple = None) -> list[dict]:
    """Prompt for sets with AI suggestions."""
    # Interactive set entry
    # Shows: suggested weight, suggested reps
    # User can accept defaults or override
    # Returns: [{'weight': X, 'reps': Y, 'rpe': Z}, ...]
```

---

## Configuration

### Settings (`src/config/settings.py`)

```python
class Settings:
    PROJECT_ROOT = "/Users/.../traininglogs"
    DATA_DIR = PROJECT_ROOT / "data"
    DB_DIR = DATA_DIR / "database"
    
    DB_PATH = DB_DIR / "traininglogs.db"
    OUTPUT_DIR = DATA_DIR / "output"
    SESSIONS_DIR = OUTPUT_DIR / "sessions"
    
    def get_db_path() -> str
    def get_output_dir() -> str
    def get_sessions_dir() -> str
```

**Initializes Required Directories:**
```
data/
  database/        # SQLite database
  output/
    sessions/      # JSON exports
    logs/          # Logs
```

---

## Data Flow

### New Exercise Workflow

```
User enters exercise name
    ↓
Agent.prepare_exercise_logging(name)
    ├─ HistoryService.is_new_exercise()  → True
    ├─ HistoryService.get_last_weight()  → None
    ├─ ProgressionService.suggest_next_weight() → None
    └─ Returns LoggingContext(is_new=True, last_weight=None, suggested_weight=None)
    ↓
CLI shows "✨ New exercise - no history to reference"
    ↓
User enters sets with no suggestions
    ↓
Agent.log_exercise(session, name, warmup_sets, working_sets)
    ├─ ExerciseService.build_exercise()
    ├─ ExerciseService.validate_exercise()
    └─ SessionService.add_exercise()
    ↓
Session has new exercise
```

### Existing Exercise Workflow

```
User enters "Bench Press"
    ↓
Agent.prepare_exercise_logging("Bench Press")
    ├─ HistoryService.is_new_exercise()  → False
    ├─ HistoryService.get_last_exercise() → ExerciseOccurrence(weight=100, reps=5, days_ago=3)
    ├─ HistoryService.get_max_weight() → 115
    ├─ ProgressionService.suggest_next_weight() → ProgressionSuggestion(weight=102.5, 
    │                                               reasoning="RPE was 8, increase by 2.5kg",
    │                                               confidence=9)
    └─ Returns LoggingContext(is_new=False, last_weight=100, 
                             suggested_weight=102.5, suggested_reps_range=(4,6))
    ↓
CLI shows:
    📋 Logging: Bench Press
    📚 Last: 100kg (logged 3 days ago)
    ⭐ Max ever: 115kg
    💡 Suggested: 102.5kg
       Rep range: 4-6 reps
    ↓
User enters sets (accepts suggestions or changes)
    ↓
Agent validates and adds to session
    ↓
Session updated with exercise
```

---

## Design Benefits

### 1. **Testability**
- Services are pure functions (mock-friendly)
- Agent is mockable (all dependencies injected)
- DataSource is abstract (easy to stub)
- No side effects, no global state

### 2. **Maintainability**
- Each service has single responsibility
- Business logic not scattered across CLI
- Changes to history querying only affect HistoryService
- Changes to progression only affect ProgressionService

### 3. **Extensibility**
- New services can be added without changing CLI
- New AI capabilities (analytics, patterns) = new services + update Agent
- Can swap DataSource implementation (database ↔ JSON ↔ API)
- CLI stays thin and simple

### 4. **User Experience**
- Smart prompting with history context
- Intelligent suggestions based on past workouts
- Error handling with recovery hints
- Guided but not restrictive (can override suggestions)

### 5. **Code Reuse**
- Services work with CLI, API, batch processing
- ExerciseService doesn't know it's called from prompts
- ProgressionService used by Agent and tests
- Agent can be used by CLI, API, or even other agents

---

## Testing Strategy

### Unit Tests
Test each service in isolation with mocked DataSource:
```python
def test_history_service_new_exercise():
    mock_data_source = Mock()
    mock_data_source.get_last_exercise("Bench Press").return_value = None
    
    service = HistoryService(mock_data_source)
    assert service.is_new_exercise("Bench Press") == True
```

### Integration Tests
Test Agent with real services and mocked persistence:
```python
def test_agent_logs_exercise():
    # Setup services with test data
    # Create agent
    # Test prepare_workout_session → prepare_exercise_logging → log_exercise
    # Verify session state
```

### End-to-End Tests
Test complete CLI workflow with test database:
```bash
python scripts/init_db.py  # Setup test DB
python -m src.cli.main     # Run CLI with inputs
# Verify: session saved to DB + JSON exported
```

---

## Migration from Old Architecture

### Old Code (What We Had)
```
CLI
  ├─ SessionManager (stores session, weak)
  ├─ ExerciseBuilder (prompts + building, mixed concerns)
  └─ Direct database access (no abstraction)
```

**Problems:**
- SessionManager just stored data, didn't orchestrate
- ExerciseBuilder mixed UI (prompts) with logic (building)
- No abstraction for data access
- Business logic scattered across CLI

### New Code (What We Built)
```
CLI (only I/O)
  ↓
WorkoutAgent (orchestration)
  ├─ HistoryService (query exercise history)
  ├─ ProgressionService (suggest progression)
  ├─ ExerciseService (build exercises)
  └─ SessionService (manage session state)
       ↓
    DataSource (abstraction)
       └─ Persistence (database, JSON)
```

**Benefits:**
- Agent orchestrates complete workflow
- Services are pure and testable
- DataSource abstracts storage
- CLI is thin and focused

---

## Files Reference

| File | Purpose | Lines |
|------|---------|-------|
| `src/repository/data_source.py` | Abstract data interface | 180 |
| `src/repository/hybrid_data_source.py` | Database + JSON queries | 330 |
| `src/services/history_service.py` | Exercise history queries | 180 |
| `src/services/progression_service.py` | Weight/rep suggestions | 250 |
| `src/services/exercise_service.py` | Exercise building (pure) | 200 |
| `src/services/session_service.py` | Session state management | 180 |
| `src/agent/workout_agent.py` | Orchestrator & intelligence | 370 |
| `src/cli/main.py` | Thin I/O layer (refactored) | 167 |
| `src/cli/prompts.py` | User prompts (updated) | ~250 |
| `src/config/settings.py` | Configuration & paths | 60 |
| `scripts/init_db.py` | Database initialization | 50 |

**Total New Code:** ~1,500 lines of clean, well-documented Python

---

## Next Steps

### Phase 1: Testing (In Progress ✅)
- [x] Create all services
- [x] Create agent
- [x] Refactor CLI
- [x] Integration test
- [ ] Add error path tests
- [ ] Test with real user input

### Phase 2: Validation & Polish
- [ ] Test persistence (DB + JSON)
- [ ] Test error recovery hints
- [ ] Verify all prompts work
- [ ] Performance testing with large history

### Phase 3: Analytics Extension
- Create `AnalyticsAgent(WorkoutAgent)` for:
  - Volume trends
  - Strength progression
  - Deload recommendations
  - Injury prevention patterns

### Phase 4: API Layer
- REST endpoints wrapping Agent methods
- Same business logic, different interface

---

## Conclusion

This redesign transforms the codebase from a monolithic, tightly-coupled system to a clean, service-based architecture with agent orchestration. 

**Result:** A maintainable, testable, extensible system that provides intelligent user experiences while keeping the code organized and professional.
