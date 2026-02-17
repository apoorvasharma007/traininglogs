````markdown
# CODEBASE_RULES.md

Governance rules for the traininglogs codebase.

## Core Principles

✅ **Business logic is separate from CLI**
- No prompts/input in `core/`, `persistence/`, `analytics/`, `history/`
- All user interaction in `cli/` or `scripts/`

✅ **All validation in one place**
- `core/validators.py` is the single source of validation logic
- No ad-hoc validation in other modules

✅ **All database access via repository**
- `persistence/repository.py` is the only module that imports `database.py`
- No direct SQL in `core/`, `history/`, or `analytics/`

✅ **Datamodel integrity first**
- The `data_class_model/` defines the contract
- Never modify without a migration entry in MIGRATIONS.md
- Always validate before saving

✅ **No circular imports**
- `cli/` can import from all layers
- `core/` can import from `persistence/`
- `persistence/` has no dependencies on `core/` or `cli/`

✅ **No hardcoded paths**
- Use `config/settings.py` for all paths
- Use environment variables for overrides

## Code Style

- **Max file length:** 500 lines
- **Linting:** `ruff` with line length 88
- **Formatting:** `black` with line length 88
- **Type hints:** Lightweight, not strict enforcement

```bash
# Format code
black --line-length=88 .

# Lint code
ruff check --line-length=88 .
```

## Module Responsibilities

### `cli/`
- `main.py`: Application entry point, orchestrates workflow
- `prompts.py`: All user prompts and display logic

**Rules:**
- No business logic
- Import from `core/`, `persistence/`, `config/`, `history/`, `analytics/`
- Catch and display errors gracefully

### `core/`
- `session_manager.py`: Session lifecycle management
- `exercise_builder.py`: Interactive exercise construction
- `validators.py`: All validation rules

**Rules:**
- No CLI imports
- No database imports (use repository via session_manager)
- Pure functions for logic, classes for state

### `persistence/`
- `database.py`: SQLite connection and schema init
- `migrations.py`: Schema version management
- `repository.py`: All database queries and writes

**Rules:**
- No business logic
- No validation (pass invalid data to raising ValidationError in caller)
- Only raw data in/out

### `history/`
- `history_service.py`: Exercise history queries

**Rules:**
- Read-only
- Uses repository layer only
- No writes to database

### `analytics/`
- `basic_queries.py`: Analysis and reporting queries

**Rules:**
- Read-only
- No writes to database
- Returns formatted data or strings

### `config/`
- `settings.py`: Configuration and environment variables

**Rules:**
- Single source of truth for app settings
- Use for paths, phases, defaults

### `scripts/`
- Standalone executable scripts

**Rules:**
- Can be run from command line
- Minimal, focused use cases

## Database Rules

✅ **Always use migrations**
- Document schema changes in docs/development/MIGRATIONS.md
- Update migrations.py with version logic
- Test migration path before release

✅ **Use repository for persistence**
```python
# Good
repository.save_session(session_id, session_data)

# Bad
db.execute("INSERT INTO training_sessions...")
```

✅ **Never silently discard user input**
- Always validate before save
- Raise ValidationError with clear message if invalid
- Never truncate or alter data

## Testing

Current approach: Manual testing via CLI.

Future: Add unit tests in `tests/` following same layer separation.

## Documentation

- Add docstrings to all public methods
- Update README.md when adding features
- Update architecture docs in `docs/` for structural changes
- Update `.agent/PROTOCOL.md` for new agent workflows

## Git Commit Messages

Clear and atomic:
```
Implement SessionManager #6

- Add session lifecycle methods
- Integrate with repository layer
- Add docstrings
```

Not:
```
update code
fix stuff
progress
```

````
