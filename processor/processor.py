# main.py
import json
from parser.one_extract_relevant_fields import TrainingMarkdownParser
from parser.two_parse_relevant_fields_into_objects import DeepTrainingParser
# from dataclasses import is_dataclass
# from datamodels.models import TrainingSession
from pprint import pprint

# TODO: add code to setup sys.path so that parser and datamodels are importable from root path
# TODO: modify code to Load markdown training log from root path/training_logs_raw_md/*.md
# Put your markdown file path here or load content as string
with open("updated_markdown.md", "r", encoding="utf-8") as f:
    md_text = f.read()

# Step 1: Extract relevant blocks (intermediate dict)
base_parser = TrainingMarkdownParser(md_text)
intermediate = base_parser.parse()

print(">>> Intermediate dict (from markdown):")
pprint(intermediate, width=160)

# Step 2: Deep parse into dataclass objects
deep_parser = DeepTrainingParser(intermediate)
session_obj = deep_parser.build_training_session()

# Utility to convert nested dataclasses/enums into primitives for JSON
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

# Optional: call your local null-removal function here
# primitive_dict = remove_nulls(primitive_dict)

# Print python dict
print("\n>>> Final Python dict (dataclass -> primitives):")
pprint(primitive_dict, width=160)

# Convert to JSON (string)
json_out = json.dumps(primitive_dict, indent=2)
print("\n>>> JSON output preview:")
print(json_out[:2000])  # preview first n characters; save or write to file if needed

# TODO: write output file to root path/traning_logs_output/session_output.json
with open("session_output.json", "w", encoding="utf-8") as of:
    of.write(json_out)