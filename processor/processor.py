# main.py
import os
import sys
import json
from pprint import pprint

# -------------------------------------------------------------------
# ✅ Add root path so imports like `parser.*` and `datamodels.*` work
# -------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# -------------------------------------------------------------------
# ✅ Import parsers and models
# -------------------------------------------------------------------
from parser.one_extract_relevant_fields import TrainingMarkdownParser
from parser.two_parse_relevant_fields_into_objects import DeepTrainingParser
# from datamodels.models import TrainingSession   # Uncomment if needed for type hints


# -------------------------------------------------------------------
# ✅ Load the markdown training log dynamically
# -------------------------------------------------------------------
# Define folder paths relative to project root
RAW_LOGS_DIR = os.path.join(ROOT_DIR, "training_logs_raw_md")
OUTPUT_DIR = os.path.join(ROOT_DIR, "training_logs_output")

# Pick the first markdown file in training_logs_raw_md (or specify one explicitly)
md_files = [f for f in os.listdir(RAW_LOGS_DIR) if f.endswith(".md")]
if not md_files:
    raise FileNotFoundError(f"No markdown training logs found in: {RAW_LOGS_DIR}")

md_path = os.path.join(RAW_LOGS_DIR, md_files[0])

with open(md_path, "r", encoding="utf-8") as f:
    md_text = f.read()

print(f">>> Loaded training log: {md_path}\n")


# -------------------------------------------------------------------
# ✅ Step 1: Extract relevant blocks (intermediate dict)
# -------------------------------------------------------------------
base_parser = TrainingMarkdownParser(md_text)
intermediate = base_parser.parse()

print(">>> Intermediate dict (from markdown):")
pprint(intermediate, width=160)


# -------------------------------------------------------------------
# ✅ Step 2: Deep parse into dataclass objects
# -------------------------------------------------------------------
deep_parser = DeepTrainingParser(intermediate)
session_obj = deep_parser.build_training_session()


# -------------------------------------------------------------------
# ✅ Utility: Convert nested dataclasses/enums into primitives for JSON
# -------------------------------------------------------------------
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


primitive_dict = to_primitive(session_obj)

# -------------------------------------------------------------------
# ✅ Optional: remove nulls if you have a local util
# -------------------------------------------------------------------
# from utils.cleaners import remove_nulls
# primitive_dict = remove_nulls(primitive_dict)

# -------------------------------------------------------------------
# ✅ Print Python dict
# -------------------------------------------------------------------
print("\n>>> Final Python dict (dataclass -> primitives):")
pprint(primitive_dict, width=160)


# -------------------------------------------------------------------
# ✅ Convert to JSON string
# -------------------------------------------------------------------
json_out = json.dumps(primitive_dict, indent=2)

print("\n>>> JSON output preview:")
print(json_out[:2000])  # preview first 2000 chars


# -------------------------------------------------------------------
# ✅ Write output file to /training_logs_output/session_output.json
# -------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)
output_path = os.path.join(OUTPUT_DIR, "session_output.json")

with open(output_path, "w", encoding="utf-8") as of:
    of.write(json_out)

print(f"\n>>> JSON written to: {output_path}")