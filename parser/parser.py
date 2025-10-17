# app/parser.py
import re
from collections import defaultdict
from typing import Dict, Any, List

class WorkoutParser:
    """
    Parses a raw text workout log into a structured dictionary.

    This class handles the logic for reading the specific text format,
    extracting key-value pairs, and organizing exercises and their sets
    into a nested dictionary format, ready for ingestion.
    """

    def parse(self, text: str) -> Dict[str, Any]:
        """
        Main method to parse the workout text.

        Args:
            text: The raw string content of the workout log.

        Returns:
            A dictionary representing the structured workout data.
        """
        # Find the content between BEGIN: and END
        match = re.search(r"BEGIN:(.*?)END", text, re.DOTALL | re.IGNORECASE)
        if not match:
            return {}
        
        content = match.group(1).strip()
        lines = [line.strip() for line in content.split('\n') if line.strip()]

        session_data: Dict[str, Any] = {"exercises": []}
        current_exercise: Dict[str, Any] = {}
        multiline_key = None

        for line in lines:
            # Check for main session keywords first
            if re.match(r"Date:", line, re.IGNORECASE):
                multiline_key = None
                session_data['date'] = line.split(':', 1)[1].strip()
                continue
            if re.match(r"Phase:", line, re.IGNORECASE):
                multiline_key = None
                session_data['phase'] = int(line.split(':', 1)[1].strip())
                continue
            if re.match(r"Week:", line, re.IGNORECASE):
                multiline_key = None
                session_data['week'] = int(line.split(':', 1)[1].strip())
                continue
            if re.match(r"Deload:", line, re.IGNORECASE):
                multiline_key = None
                session_data['is_deload_week'] = line.split(':', 1)[1].strip().lower() == 'yes'
                continue
            if re.match(r"Focus:", line, re.IGNORECASE):
                multiline_key = None
                session_data['focus'] = line.split(':', 1)[1].strip()
                continue
            if re.match(r"Duration:", line, re.IGNORECASE):
                multiline_key = None
                duration_str = line.split(':', 1)[1].strip()
                session_data['session_duration_minutes'] = int(re.sub(r'\s*min', '', duration_str, flags=re.IGNORECASE))
                continue

            # Check for a new exercise
            ex_match = re.match(r"(?:EX|Exercise)(\d+):\s*(.+)", line, re.IGNORECASE)
            if ex_match:
                multiline_key = None
                if current_exercise:
                    session_data["exercises"].append(current_exercise)
                current_exercise = {
                    "number": int(ex_match.group(1)),
                    "name": ex_match.group(2).strip(),
                    "warmup_sets": [],
                    "working_sets": []
                }
                continue

            # If we are in a multiline block, append the line
            if multiline_key:
                if multiline_key == "warmup_notes":
                    current_exercise["warmup_notes"] = current_exercise.get("warmup_notes", "") + line + "\n"
                    continue
                if multiline_key == "exercise_notes":
                    current_exercise["notes"] = current_exercise.get("notes", "") + line + "\n"
                    continue
                if multiline_key == "form_cues":
                    current_exercise.setdefault("form_cues", []).append(line)
                    continue

            # Check for exercise-level keywords
            goal_match = re.match(r"Goal:\s*([\d.]+)\s*kg\s*x\s*(\d+)\s*sets\s*x\s*(\d+)-(\d+)\s*reps", line, re.IGNORECASE)
            if goal_match:
                current_exercise["current_goal"] = {
                    "weight_kg": float(goal_match.group(1)),
                    "sets": int(goal_match.group(2)),
                    "rep_range": {
                        "min": int(goal_match.group(3)),
                        "max": int(goal_match.group(4))
                    }
                }
                continue

            rest_match = re.match(r"Rest:\s*(\d+)\s*min", line, re.IGNORECASE)
            if rest_match:
                if "current_goal" in current_exercise: # Assume rest belongs to goal
                     current_exercise["current_goal"]["rest_minutes"] = int(rest_match.group(1))
                continue

            # Warmup Notes
            if re.match(r"WarmupNotes:", line, re.IGNORECASE):
                multiline_key = "warmup_notes"
                continue
            # Exercise Notes
            if re.match(r"ExerciseNotes:", line, re.IGNORECASE):
                multiline_key = "exercise_notes"
                continue
            # Cues
            if re.match(r"Cues:", line, re.IGNORECASE):
                multiline_key = "form_cues"
                continue

            # Warmup Sets
            warmup_match = re.match(r"(?:W|WarmupSet)(\d+):\s*([\d.]+)\s*x\s*(\d+|feel)(?:\s*-\s*(.+))?", line, re.IGNORECASE)
            if warmup_match:
                multiline_key = None
                set_num, weight, reps, note = warmup_match.groups()
                warmup_set = {
                    "number": int(set_num),
                    "weight_kg": float(weight),
                    "rep_count": int(reps) if reps.isdigit() else None,
                    "notes": note.strip() if note else None
                }
                current_exercise["warmup_sets"].append(warmup_set)
                continue

            # Working Sets (this is the most complex one)
            set_match = re.match(r"(?:S|Set)(\d+):", line, re.IGNORECASE)
            if set_match:
                multiline_key = None
                set_num = int(set_match.group(1))
                remainder = line.split(":", 1)[1].strip()
                
                working_set = self._parse_working_set(set_num, remainder)
                current_exercise["working_sets"].append(working_set)
                continue
        
        # Add the last exercise to the list
        if current_exercise:
            # Clean up multiline notes by removing the last newline
            for key in ['warmup_notes', 'notes']:
                if key in current_exercise and current_exercise[key]:
                    current_exercise[key] = current_exercise[key].strip()
            session_data["exercises"].append(current_exercise)
            
        return session_data

    def _parse_working_set(self, set_num: int, line_part: str) -> Dict[str, Any]:
        """Helper to parse the complex working set line."""
        
        parts = line_part.split()
        set_data: Dict[str, Any] = {"number": set_num}
        
        # 1. Weight x Reps[+Partials]
        weight_rep_match = re.match(r"([\d.]+)\s*x\s*(\d+)(?:\+(\d+))?", parts[0], re.IGNORECASE)
        if not weight_rep_match:
            raise ValueError(f"Could not parse weight/reps for set {set_num}: {parts[0]}")
        
        weight, full_reps, partial_reps = weight_rep_match.groups()
        set_data["weight_kg"] = float(weight)
        set_data["rep_count"] = {"full": int(full_reps), "partial": int(partial_reps) if partial_reps else 0}
        
        # 2. Parse remaining optional parts
        remaining_parts = " ".join(parts[1:])
        
        # RPE
        rpe_match = re.search(r"RPE\s*([\d.]+)", remaining_parts, re.IGNORECASE)
        if rpe_match:
            set_data["rpe"] = float(rpe_match.group(1))
            remaining_parts = remaining_parts.replace(rpe_match.group(0), "").strip()

        # Quality
        quality_match = re.search(r"\b(perfect|good|bad|learning)\b", remaining_parts, re.IGNORECASE)
        if quality_match:
            set_data["rep_quality_assessment"] = quality_match.group(1).lower()
            remaining_parts = remaining_parts.replace(quality_match.group(0), "").strip()
            
        # Failure Technique
        failure_match = re.search(r"failure:\s*(\w+\(.*\))", remaining_parts, re.IGNORECASE)
        if failure_match:
            set_data["failure_technique_raw"] = failure_match.group(1) # Pass raw string to ingestor
            remaining_parts = remaining_parts.replace(failure_match.group(0), "").strip()
            
        # Notes (anything after a '-')
        note_match = re.search(r"-\s*(.*)", remaining_parts, re.IGNORECASE)
        if note_match:
            set_data["notes"] = note_match.group(1).strip()
            
        return set_data