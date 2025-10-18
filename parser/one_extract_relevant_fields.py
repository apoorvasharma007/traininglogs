# Extract relevant fields from simplified Markdown training logs for further parsing.
import re
from typing import Dict, Any

class TrainingMarkdownParser:
    """
    Parse the simplified Markdown into a hierarchical dict:
      {
        "metadata": { ... },
        "exercises": [ { name, goal, rest, warmup_sets: [...], warmup_notes, working_sets: [...], notes, cues } ]
      }
    """

    def __init__(self, text: str):
        self.lines = [l.rstrip() for l in text.splitlines()]
        self.parsed_data = {"metadata": {}, "exercises": []}

    def parse(self) -> Dict[str, Any]:
        current_ex = None
        current_section = None

        for line in self.lines:
            if not line.strip():
                continue

            # Metadata lines before the first exercise
            if line.startswith("- ") and not current_ex:
                key, value = self._parse_metadata_line(line)
                self.parsed_data["metadata"][key] = value
                continue

            # New exercise header
            if re.match(r"^##\s*Exercise\s*\d+", line):
                if current_ex:
                    self.parsed_data["exercises"].append(current_ex)
                current_ex = {"warmup_sets": [], "working_sets": [], "cues": []}
                current_section = "exercise_header"
                continue

            # Section headers (### and ####)
            if line.startswith("### "):
                current_section = line[4:].strip().lower().replace(" ", "_")
                continue
            if line.startswith("#### "):
                current_section = line[5:].strip().lower().replace(" ", "_")
                continue

            # Bolded key-value pairs in header
            if line.startswith("**") and current_section == "exercise_header":
                k, v = self._parse_key_value_line(line)
                if k and v is not None:
                    current_ex[k] = v
                continue

            # Warmup numbered lines
            if current_section == "warmup" and re.match(r"^\d+\.", line.strip()):
                current_ex["warmup_sets"].append(line.strip())
                continue

            # Warmup notes (accumulate)
            if current_section == "warmup_notes":
                current_ex["warmup_notes"] = (current_ex.get("warmup_notes", "") + " " + line.strip()).strip()
                continue

            # Working sets numbered lines
            if current_section == "working_sets" and re.match(r"^\d+\.", line.strip()):
                current_ex["working_sets"].append(line.strip())
                continue

            # Notes (accumulate)
            if current_section == "notes":
                current_ex["notes"] = (current_ex.get("notes", "") + " " + line.strip()).strip()
                continue

            # Cues are bullet lines under Cues
            if current_section == "cues" and line.strip().startswith("- "):
                cue = line.strip()[2:].strip()
                current_ex.setdefault("cues", []).append(cue)
                continue

        # append last exercise
        if current_ex:
            self.parsed_data["exercises"].append(current_ex)

        return self.parsed_data

    def _parse_metadata_line(self, line: str):
        # "- Key: value"
        key, value = [p.strip() for p in line[2:].split(":", 1)]
        return key.lower(), value

    def _parse_key_value_line(self, line: str):
        # "**Name:** Bench Press"
        m = re.match(r"\*\*(.+?):\*\*\s*(.+)", line)
        if not m:
            return None, None
        return m.group(1).strip().lower(), m.group(2).strip()