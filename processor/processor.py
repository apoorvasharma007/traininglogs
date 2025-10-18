# main.py
import os
import sys
import json
from pprint import pprint
# utils/cleaners.py

from dataclasses import is_dataclass, asdict

def remove_nulls(obj):
    """
    Recursively remove all keys with None values from nested dicts, lists, or dataclasses.
    Returns a cleaned copy of the structure.
    """
    # Convert dataclasses to dicts first
    if is_dataclass(obj):
        obj = asdict(obj)

    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            v_clean = remove_nulls(v)
            # keep only non-null, non-empty values
            if v_clean is not None and v_clean != {} and v_clean != []:
                cleaned[k] = v_clean
        return cleaned

    elif isinstance(obj, list):
        cleaned_list = [remove_nulls(i) for i in obj if i is not None]
        return [i for i in cleaned_list if i != {} and i != []]

    else:
        return obj
    
# -------------------------------------------------------------------
# ✅ Add project root (parent of this folder) to sys.path so imports like
# `parser.*` and `datamodels.*` resolve when running this script directly.
#
# Explanation:
#  - os.path.abspath(__file__) gives the full path to this file (processor.py)
#  - os.path.dirname(...) once returns the directory that contains this file
#    (THIS_DIR -> the `processor/` folder).
#  - os.path.dirname(THIS_DIR) returns the parent directory of `processor/`,
#    i.e. the project root where top-level packages such as `parser/`
#    and `datamodels/` live. We need to add that parent to sys.path so Python
#    can locate those packages when this script is executed directly.
#
#  - We insert the PROJECT_ROOT at the front of sys.path so the local
#    packages in the repo take precedence over any globally installed packages
#    with the same names during development.
#
# Alternative (pathlib):
#   from pathlib import Path
#   PROJECT_ROOT = Path(__file__).resolve().parent.parent
# -------------------------------------------------------------------
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    # prepend so local packages shadow any globally installed ones during dev
    sys.path.insert(0, PROJECT_ROOT)

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
# Raw logs and output live at project root
RAW_LOGS_DIR = os.path.join(PROJECT_ROOT, "input_training_logs_raw")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output_training_logs_json")

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
# ✅ Write output file to /training_logs_output/{session_id}.json
# -------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)
output_path = os.path.join(OUTPUT_DIR, f"{primitive_dict['session_id']}.json")

with open(output_path, "w", encoding="utf-8") as of:
    of.write(json_out)

print(f"\n>>> JSON written to: {output_path}")