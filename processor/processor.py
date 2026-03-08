# main.py
import os
import sys
import json
from pprint import pprint
# utils/cleaners.py

from dataclasses import is_dataclass, asdict

# -------------------------------------------------------------------
# ✅ Utility: Remove nulls from output JSON doc
# -------------------------------------------------------------------
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
# ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⠆⠀⠀⢠⡞⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡾⡇⠀⠀⠀⡿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⠟⣶⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣇⠹⣆⠀⢠⠃⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⡏⡏⠀⠘⡼⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣦⡈⠓⢾⠀⣧⡀⠀⠀⠀⠀⠀⣤⣤⣴⣶⣦⢤⣄⡀⠀⠀⢸⠀⣧⠀⠀⢧⠘⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠻⣿⣦⣼⠀⡿⡏⠙⠲⠤⣀⡀⠀⠈⠙⣆⠈⠓⣄⠙⢢⡀⠈⣆⠘⢇⠀⠸⡇⠘⣆⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠙⢻⠀⢸⣹⡀⠠⣀⠀⠉⠙⠲⢄⡈⣆⠀⠈⢣⡀⢱⣄⣸⢦⣤⣑⢄⡇⠀⠸⡆⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⡀⠘⣇⢻⣶⣌⠙⢦⡀⠀⠀⠉⠺⢦⠀⠨⡇⠀⠙⣶⣉⣴⠛⠻⠱⣄⠀⢱⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣴⣖⣉⣇⠀⠸⡄⠹⣌⠳⣦⡙⢶⣄⠀⠀⠀⠙⢆⣟⠀⡸⠫⢿⡜⣆⠀⠀⠘⢆⠈⡆⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣠⠽⣿⠀⠀⠹⡄⠈⢧⡈⠻⣆⠙⣧⣀⠀⠀⠀⠹⣄⡀⠀⡜⠳⣘⡄⠀⠀⠘⣇⡇⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⣾⣿⣛⠛⠛⠿⣦⡀⠀⠙⢤⠀⠱⣦⢽⣧⡈⢻⡇⠀⠀⢀⣹⣏⣼⡁⠀⢙⣧⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢈⡇⠀⠀⢳⡳⣀⠀⠀⢳⡄⠈⢷⣌⣷⣠⡿⣿⣫⣿⣾⣿⣄⠀⡴⠋⠙⠳⣶⣶⢬⣿⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣤⣴⣯⣤⣤⣤⣤⣷⡈⢷⣦⡀⠙⢦⠀⣈⠛⢿⣾⣿⠋⢁⠔⠚⠻⢟⠣⠀⠔⠉⠙⢮⣙⣿⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⣠⣾⠿⢭⡉⠀⠀⠀⠈⠉⠙⠛⣿⣦⡉⢿⣦⣌⢣⡈⢷⡀⡼⢿⡄⠈⠀⡠⠒⠚⠳⢄⠀⢀⠖⠙⢿⣿⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠘⠁⠀⠀⣠⣇⣠⣤⣤⣤⣤⡴⠚⢉⣿⣿⣦⡈⠙⣷⣽⣄⣿⠃⠀⠙⢷⣼⡁⠀⡀⠐⠒⠯⣉⠀⢠⠴⣿⣆⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⣠⣴⡿⠛⠋⠉⠁⠉⢹⠟⠀⠀⠀⣠⣽⣿⣷⡀⠸⠿⢿⡇⠀⠀⠀⠀⢹⣷⣦⣇⠀⢀⠘⠙⠛⡇⠀⠸⣿⣿⡀⠀⠀⠀
# ⠀⠀⠀⠀⢀⣼⣯⣅⠀⠀⠀⠀⣀⡴⠋⠀⠐⠒⠉⠉⠉⠛⣿⣷⣄⡀⢸⣧⠀⠀⠀⠀⠀⢻⣿⣿⣿⣾⠀⠀⠀⠀⡄⠀⡇⠈⣧⠀⠀⠀
# ⠀⠀⠀⢀⠟⠁⠀⣸⣠⡴⠾⢿⠟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠨⢟⣛⣿⡟⠉⢳⣄⠀⠀⠀⠀⢻⡈⠉⠻⣷⣀⠀⠀⢸⣼⣇⣧⡿⠀⠀⠀
# ⠀⠀⠀⠀⢀⡴⠞⠋⠀⠀⢠⠞⠀⠀⠀⠀⢀⣠⠤⢔⣾⣿⠿⠛⢿⢹⠁⠀⠀⠙⢷⡄⠀⠀⠀⠙⠻⣿⣿⡟⣟⠛⠁⣿⠀⣿⠁⠀⠀⠀
# ⠀⠀⠀⣰⠟⠁⠀⠀⢀⣠⠏⠀⠀⠀⣠⠖⠋⣠⣾⡟⠛⣧⠀⠀⠘⢿⡄⠀⠀⠀⠀⠳⠀⠀⠀⠀⠀⠈⢿⣇⠹⠀⠀⢸⡀⣿⠀⠀⠀⠀
# ⠀⠀⢰⣏⣄⠀⣠⣶⢿⠏⠀⠀⠀⠞⠁⣠⣾⡿⡏⠀⠀⠈⠳⣄⣀⣀⣻⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⢦⠀⠀⠘⢇⢹⠀⠀⠀⠀
# ⠀⠀⡿⠁⣰⡾⠛⠀⡜⠀⠀⠀⠀⢀⣼⡿⠃⠘⢳⡀⠀⠀⢠⠋⠳⢄⡀⠙⢦⣀⠀⠀⠀⢀⠀⠀⠀⠀⠀⠙⠾⠀⠀⠀⠈⠋⣇⠀⠀⠀
# ⠀⠀⠁⣼⠛⠀⠀⣸⠃⠀⠀⠀⢀⣾⡟⣷⠀⠀⠀⠙⠒⠒⠚⢷⠖⠋⢉⡿⠋⠉⠓⢦⣄⠸⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⡆⠀⠀
# ⠀⠀⣸⠃⠀⢀⣴⡇⠀⠀⠀⢀⣾⡟⠉⠉⢧⡀⠀⠀⠘⣆⣀⠤⢷⣶⠟⠀⠀⠀⠀⠀⠈⠱⣄⠉⠳⢤⡀⠀⠀⠀⢰⡎⠉⠲⠄⢹⠲⡄
# ⠀⠀⣧⠞⣧⣾⢿⠁⠀⠀⠀⣼⡿⡁⠀⠀⠀⠈⠹⡟⠛⠙⣆⡤⣾⡟⠀⠀⠀⠀⠀⠀⠀⠀⠈⢳⡀⠀⠙⢦⡀⠀⢀⣿⣄⠀⠀⠀⠀⢸
# ⠀⢸⠃⣰⡟⠁⣾⠀⠀⠀⢸⣿⣤⠧⣄⠀⠀⠀⢀⣱⠤⠒⠁⢠⡿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢦⣵⡄⢻⠀⠸⡻⣿⣄⣤⠀⠀⡼
# ⠀⠉⢸⡟⠀⠀⡿⠀⠀⠀⣿⡇⠀⠀⠀⠉⢹⡏⠉⠈⣷⠤⠴⣿⢻⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⢷⠀⢧⡀⠀⠾⠀⠀⢸⢠⠇
# ⠀⠀⡿⠁⠀⠀⡇⠀⠀⢰⡟⢱⣄⠀⠀⠀⠀⢣⠤⠚⠁⠀⢰⣿⠘⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⠷⣄⡉⠳⢦⣀⡤⣾⡟⠀
# ⠀⢸⣇⡤⠤⣄⡇⠀⠀⣿⡏⠉⠈⠙⠒⡖⠒⠉⢷⡀⠀⣠⢾⡟⠀⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠁⠀⠀⠀⠈⠉⠛⠉⢻⠖⠋⠀⠀
# ⠀⣼⠏⠀⢀⣿⡇⠀⢀⣿⡀⠀⠀⠀⠀⠙⣆⣀⠴⠋⠉⠑⢾⡇⠀⢸⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⢹⠀⢀⣿⠏⣇⠀⢸⣿⢑⡤⣀⣀⣀⡴⠛⣇⠀⠀⠀⢀⣼⡇⠀⠸⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⣼⡏⠀⣧⠀⣼⡿⠉⠀⠈⠉⢧⡀⠀⢈⡷⠒⠒⠫⣼⡇⠀⠀⢿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⢠⣿⣠⢦⣿⠀⣿⣧⠀⠀⠀⠀⠀⢉⣞⠉⠀⠀⠀⠀⢸⣧⠀⠀⠈⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⣿⠁⢸⣿⢰⣿⣏⡳⠤⣤⡤⠖⠉⠘⢦⡀⠀⠀⣠⡾⣿⠀⠀⠀⠸⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠋⠀⡞⣿⢸⣿⠀⠀⠀⠈⠣⡀⠀⢀⣠⠛⠉⠉⠉⠓⣿⡄⠀⠀⠀⠘⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⢰⠇⡿⢸⣿⡄⠀⠀⠀⠀⢈⣽⡋⠀⠀⠀⠀⠀⠀⣿⡇⠀⠀⠀⠀⠈⢧⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⢿⣠⡇⢸⣿⠿⠓⠦⢶⡛⠉⠀⠙⠢⣤⣀⣀⣀⡤⣿⣿⡄⠀⠀⠀⠀⠀⠻⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠸⢻⡇⣸⡇⠀⠀⠀⠀⠳⡀⠀⢀⡴⠛⠀⠀⠀⠀⠀⢸⣷⡀⠀⠀⠀⠀⠀⠹⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⣾⠃⣿⡇⠀⠀⠀⠀⠀⢈⣿⣏⠀⠀⠀⠀⠀⠀⠀⢸⠿⣷⡀⠀⠀⠀⠀⠀⠈⠛⢶⣄⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⢠⡇⠀⣿⣿⣦⣤⣤⣶⠟⠁⠈⠈⠳⢤⣀⣀⣀⡤⠴⠚⠚⠛⣷⡄⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠳⢤⣄⡀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⣾⠁⢸⣿⢟⠩⠃⠈⢧⠀⠀⠀⠀⢀⡼⠋⠀⠀⠀⠀⠀⠀⠀⠘⣿⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠙⢶⡀⠀⠀⠀⠀⠀
# ⠀⠀⠀⢰⡿⠀⣾⡇⠀⠀⠀⠀⠈⢧⡀⠀⡰⠊⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⠟⢿⣷⣄⠀⠀⠀⠀⠀⠀⣀⣀⣀⡠⠤⠤⣹⡄⠀⠀⠀⠀
# ⠀⣠⣴⡏⠀⢰⣿⣧⡀⠀⠀⠀⠀⠀⣹⠿⡀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡰⠯⠤⠤⠜⠛⠙⠓⠒⠛⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠴⠁⠸⢤⠴⠟⠛⠙⠛⠶⣶⡴⠖⠊⠁⠀⠙⠲⢤⣄⣀⣀⣀⣤⠴⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢳⡄⠀⠀⠀⠀⠀⣠⠇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
# ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠲⣴⡤⠴⠚⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀

# -------------------------------------------------------------------
# ✅ Load the markdown training log dynamically - EDIT INPUT FOLDER HERE
# -------------------------------------------------------------------
# Define folder paths relative to project root
# Raw logs and output live at project root
RAW_LOGS_DIR = os.path.join(PROJECT_ROOT, "input_training_logs_md/phase 3 week 5")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output_training_logs_json")


def process_md_file(md_path: str):
    """Read a markdown file, parse it into the dataclass objects and write JSON output.

    This is intentionally simple and mirrors the original linear flow but
    packaged as a function so we can call it for every file in the folder.
    """
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    print(f">>> Loaded training log: {md_path}\n")

    # Step 1: Extract relevant blocks (intermediate dict)
    base_parser = TrainingMarkdownParser(md_text)
    intermediate = base_parser.parse()

    # Step 2: Deep parse into dataclass objects
    deep_parser = DeepTrainingParser(intermediate)
    session_obj = deep_parser.build_training_session()

    # Convert to primitives and write JSON
    primitive_dict = to_primitive(session_obj)
    json_out = json.dumps(primitive_dict, indent=2)

    # TODO: make this a separate method with unit tests
    # Build exact nested output path as requested:
    # OUTPUT_DIR / {program} / "phase {phase}" / "week {week}" / {session_id}.json
    program = primitive_dict.get("program") or "unknown_program"
    phase = primitive_dict.get("phase") or "1"
    week = primitive_dict.get("week") or "unknown"

    program_dir = os.path.join(OUTPUT_DIR, program)
    phase_dir = os.path.join(program_dir, f"phase {phase}")
    week_dir = os.path.join(phase_dir, f"week {week}")

    os.makedirs(week_dir, exist_ok=True)
    output_path = os.path.join(week_dir, f"{primitive_dict['session_id']}.json")
    with open(output_path, "w", encoding="utf-8") as of:
        of.write(json_out)

    print(f"\n>>> JSON written to: {output_path}\n")


# Pick all markdown files in RAW_LOGS_DIR and process each
md_files = [f for f in os.listdir(RAW_LOGS_DIR) if f.endswith(".md")]
if not md_files:
    raise FileNotFoundError(f"No markdown training logs found in: {RAW_LOGS_DIR}")

for md_file in md_files:
    md_path = os.path.join(RAW_LOGS_DIR, md_file)
    process_md_file(md_path)
