from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="traininglogs validate",
        description="Parse and validate a training log. Prints a model summary. No DB write.",
    )
    parser.add_argument("file", help="Path to a .md training log file")
    args = parser.parse_args(argv)

    md_path = Path(args.file).resolve()
    if not md_path.is_file():
        print(f"✗ Not a file: {md_path}")
        return 1

    from traininglogs.parser.extract import TrainingMarkdownParser
    from traininglogs.parser.parse import DeepTrainingParser
    from traininglogs.processor.processor import (
        _convert_lbs_to_kg, _derive_program_context, compute_session_id, INPUTS_DIR,
    )
    from traininglogs.models.models import TrainingSession
    from pydantic import ValidationError

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

    print(f"✓ Valid — {session.session_id}")
    print(f"  date:     {session.date}")
    print(f"  program:  {session.program}")
    print(f"  phase:    {session.phase}  week: {session.week}")
    print(f"  focus:    {session.focus}")
    print(f"  duration: {session.session_duration_minutes} min")
    print(f"  exercises: {len(session.exercises)}")
    for i, ex in enumerate(session.exercises, 1):
        n_sets = len(ex.sets) if ex.sets else 0
        ex_type = ex.exercise_type.value if hasattr(ex.exercise_type, "value") else ex.exercise_type
        print(f"    {i}. {ex.name}  ({ex_type}, {n_sets} sets)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
