import os
import sys
import json
import argparse
from pathlib import Path
from dataclasses import is_dataclass

from traininglogs.parser.extract import TrainingMarkdownParser
from traininglogs.parser.parse import DeepTrainingParser


def to_primitive(o):
    from enum import Enum
    from dataclasses import is_dataclass

    if isinstance(o, Enum):
        return o.value
    if is_dataclass(o):
        return {k: to_primitive(getattr(o, k)) for k in o.__dataclass_fields__}
    if isinstance(o, list):
        return [to_primitive(i) for i in o]
    if isinstance(o, dict):
        return {k: to_primitive(v) for k, v in o.items()}
    return o


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INPUT_LOGS_DIR = PROJECT_ROOT / "input_training_logs_md"
OUTPUT_DIR = PROJECT_ROOT / "output_training_logs_json"


def process_md_file(md_path: Path) -> None:
    """Read a markdown file, parse it into dataclass objects and write JSON output."""
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    print(f">>> Loaded training log: {md_path}\n")

    base_parser = TrainingMarkdownParser(md_text)
    intermediate = base_parser.parse()

    deep_parser = DeepTrainingParser(intermediate)
    session_obj = deep_parser.build_training_session()

    primitive_dict = to_primitive(session_obj)
    json_out = json.dumps(primitive_dict, indent=2)

    # TODO: make this a separate method with unit tests
    program = primitive_dict.get("program") or "unknown_program"
    phase = primitive_dict.get("phase") or "1"
    week = primitive_dict.get("week") or "unknown"

    week_dir = OUTPUT_DIR / program / f"phase {phase}" / f"week {week}"
    week_dir.mkdir(parents=True, exist_ok=True)

    output_path = week_dir / f"{primitive_dict['session_id']}.json"
    with open(output_path, "w", encoding="utf-8") as of:
        of.write(json_out)

    print(f">>> JSON written to: {output_path}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Process training logs for a given phase and week.")
    parser.add_argument("--phase", type=int, default=3, help="Phase number (default: 3)")
    parser.add_argument("--week", type=int, default=5, help="Week number (default: 5)")
    args = parser.parse_args()

    raw_logs_dir = INPUT_LOGS_DIR / f"phase {args.phase} week {args.week}"

    if not raw_logs_dir.exists():
        print(f"Error: directory not found: {raw_logs_dir}", file=sys.stderr)
        sys.exit(1)

    md_files = list(raw_logs_dir.glob("*.md"))
    if not md_files:
        print(f"Error: no markdown files found in {raw_logs_dir}", file=sys.stderr)
        sys.exit(1)

    for md_path in md_files:
        process_md_file(md_path)


if __name__ == "__main__":
    main()
