# ai

## Purpose
Single place for LLM integration and interpretation logic.

## Main Modules
- `llm_provider.py`: provider adapters (Ollama/OpenAI/disabled).
- `conversational_ai_service.py`: parsing/rewrite behavior.
- `llm_interpreter_service.py`: app-facing LLM boundary interface.

## Boundary
- Produces structured intents from natural language.
- Does not mutate session state directly.
