# cli

## Purpose
Terminal entrypoint and CLI interaction helpers.

## Main Modules
- `main.py`: dependency wiring and app bootstrap.
- `prompts.py`: terminal I/O helpers.
- `mobile_commands.py`: command grammar parsing and aliases.

## Boundary
- Orchestrates startup and I/O only.
- Business state changes happen in workflow/services layers.
