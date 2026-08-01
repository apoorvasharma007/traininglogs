from __future__ import annotations

from pathlib import Path
from typing import Optional


def _print_session_summary(session) -> None:
    print(f"✓ {session.session_id}  —  {len(session.exercises)} exercises")
    for i, ex in enumerate(session.exercises, 1):
        n_sets = len(ex.sets) if ex.sets else 0
        n_warmup = len(ex.warmup_sets) if ex.warmup_sets else 0
        warmup_str = f"  {n_warmup} warmup" if n_warmup else ""
        print(f"  {i}. {ex.name}  ({n_sets} sets{warmup_str})")


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="traininglogs validate",
        description="Parse and validate a training log. Prints a model summary. No DB write.",
    )
    parser.add_argument("file", help="Path to a .md training log file")
    parser.add_argument(
        "--parser",
        choices=["ai", "rules", "groq"],
        default="ai",
        help="Parser to use: 'ai' (Anthropic, default), 'groq' (free), or 'rules' (rule-based).",
    )
    args = parser.parse_args(argv)

    md_path = Path(args.file).resolve()
    if not md_path.is_file():
        print(f"✗ Not a file: {md_path}")
        return 1

    if args.parser == "ai":
        return _validate_ai(md_path)
    if args.parser == "groq":
        return _validate_groq(md_path)
    return _validate_rules(md_path)


def _validate_ai(md_path: Path) -> int:
    from dotenv import load_dotenv
    from pydantic import ValidationError

    load_dotenv()
    from traininglogs.agent.llm_orchestrator import LLMOrchestrator
    from traininglogs.processor.processor import INPUTS_DIR, build_session_from_extract

    md_text = md_path.read_text(encoding="utf-8")

    try:
        orchestrator = LLMOrchestrator()
        extract = orchestrator.run(md_text)
        session = build_session_from_extract(extract, md_path, INPUTS_DIR)
    except ValidationError as e:
        print(f"✗ Validation failed:\n{e}")
        return 1
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1

    _print_session_summary(session)
    return 0


def _validate_groq(md_path: Path) -> int:
    from dotenv import load_dotenv
    from pydantic import ValidationError

    load_dotenv()
    from traininglogs.agent.providers import GroqProvider
    from traininglogs.agent.llm_orchestrator import LLMOrchestrator
    from traininglogs.processor.processor import INPUTS_DIR, build_session_from_extract

    md_text = md_path.read_text(encoding="utf-8")

    try:
        provider = GroqProvider()
        orchestrator = LLMOrchestrator(parser_provider=provider, correction_provider=provider)
        extract = orchestrator.run(md_text)
        session = build_session_from_extract(extract, md_path, INPUTS_DIR)
    except ValidationError as e:
        print(f"✗ Validation failed:\n{e}")
        return 1
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1

    _print_session_summary(session)
    return 0


def _validate_rules(md_path: Path) -> int:
    from pydantic import ValidationError

    from traininglogs.parser.extract import TrainingMarkdownParser
    from traininglogs.parser.parse import DeepTrainingParser
    from traininglogs.processor.processor import (
        INPUTS_DIR,
        _convert_lbs_to_kg,
        _derive_program_context,
        compute_session_id,
    )
    from traininglogs.models.models import TrainingSession

    md_text = md_path.read_text(encoding="utf-8")

    try:
        base_parser = TrainingMarkdownParser(md_text)
        intermediate = base_parser.parse()

        deep_parser = DeepTrainingParser(intermediate)
        session_dict = deep_parser.build_training_session()

        path_ctx = _derive_program_context(md_path, INPUTS_DIR)
        for key, value in path_ctx.items():
            if session_dict.get(key) is None:
                session_dict[key] = value

        weight_unit = intermediate["metadata"].get("unit", "kg").lower()
        if weight_unit == "lbs":
            session_dict = _convert_lbs_to_kg(session_dict)
            session_dict["weight_unit"] = "lbs"

        date_str = intermediate["metadata"].get("date", session_dict.get("date", ""))
        session_dict["session_id"] = compute_session_id(md_path, INPUTS_DIR, date_str)

        session = TrainingSession.model_validate(session_dict)

    except ValidationError as e:
        print(f"✗ Validation failed:\n{e}")
        return 1
    except Exception as e:
        print(f"✗ Parse error: {e}")
        return 1

    _print_session_summary(session)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
