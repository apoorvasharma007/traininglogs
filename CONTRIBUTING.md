# Contributing to traininglogs

Thank you for your interest in contributing to traininglogs!

## Quick Start

1. **Read the architecture:** [docs/architecture.md](docs/architecture.md)
2. **Check the roadmap:** [TASKLIST.md](TASKLIST.md)
3. **Review code standards:** [docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md)
4. **Start working:** Use agent-assisted development workflow (see `.agency/PROTOCOL.md`)

## Development Workflow

### For Human Contributors

1. Review [TASKLIST.md](TASKLIST.md) for open tasks
2. Branch from `main`: `git checkout -b feature/task-name`
3. Follow [docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md)
4. Test your changes: `python scripts/init_db.py`
5. Run safety checks: `python .agent/scripts/verify_changes.py`
6. Submit pull request with clear description

### For Agent-Assisted Development

1. Review [.agent/PROTOCOL.md](.agent/PROTOCOL.md) for your role
2. Read the task specification in [.agent/workflows/](.agent/workflows/)
3. Follow module responsibilities in [docs/development/CODEBASE_RULES.md](docs/development/CODEBASE_RULES.md)
4. Test locally before submission
5. Run `python .agent/scripts/verify_changes.py` to verify safety

## Code Standards

- **No business logic in CLI** — Use `core/` for logic
- **All validation in one place** — Add to `core/validators.py`
- **Database access via repository** — No direct SQL outside `persistence/`
- **No circular imports** — See dependency rules in docs/development/CODEBASE_RULES.md
- **Max 500 lines per file** — Split large files
- **Type hints on public methods** — Lightweight, not strict
- **Docstrings on all public functions** — Include examples where helpful

## Testing

Current approach: Manual CLI testing.

```bash
# Initialize database
python scripts/init_db.py

# Run application
python -m cli.main

# Test imports (no circular deps)
python -c "import cli.main; print('OK')"

# Safety verification
python .agent/scripts/verify_changes.py
```

## Reporting Issues

1. Check [TASKLIST.md](TASKLIST.md) — your issue may already be tracked
2. Describe the problem clearly
3. Include:
   - What you expected
   - What happened
   - Steps to reproduce
   - Python version and OS

## Community

- **Architecture questions:** See [docs/](docs/) folder
- **Agent governance:** See [.agent/](.agent/) folder
- **Development standards:** See [docs/development/](docs/development/)

## License

This project is closed-source. Do not share code externally.

---

**Happy coding!** 🚀
