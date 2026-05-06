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

    md_path = Path(args.file)
    if not md_path.is_file():
        print(f"✗ Not a file: {md_path}")
        return 1

    from traininglogs.parser.extract import TrainingMarkdownParser
    from traininglogs.parser.parse import DeepTrainingParser
    from traininglogs.processor.processor_v2 import _to_primitive, compute_session_id
    from traininglogs.models.models_v2 import TrainingSession
    from dataclasses import is_dataclass
    from enum import Enum
    from pydantic import ValidationError

    md_text = md_path.read_text(encoding="utf-8")

    try:
        base_parser = TrainingMarkdownParser(md_text)
        intermediate = base_parser.parse()

        deep_parser = DeepTrainingParser(intermediate)
        session_obj = deep_parser.build_training_session()

        primitive_dict = _to_primitive(session_obj)

        for ex in primitive_dict.get("exercises", []):
            if "working_sets" in ex:
                raw_sets = ex.pop("working_sets") or []
                has_activity = False
                for s in raw_sets:
                    if isinstance(s, dict):
                        if "set_type" not in s:
                            s["set_type"] = "strength"
                        elif s.get("set_type") == "activity":
                            has_activity = True
                ex["sets"] = raw_sets
                if has_activity:
                    ex["exercise_type"] = "activity"

        date_str = intermediate["metadata"].get("date", primitive_dict.get("date", ""))
        session_id = compute_session_id(md_path, md_path.parent, date_str)
        primitive_dict["session_id"] = session_id

        session = TrainingSession.model_validate(primitive_dict)

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
