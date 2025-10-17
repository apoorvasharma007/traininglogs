# app/parser.py
import logging
import re
from collections import defaultdict
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

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
        
        # Keep the raw content (do not strip) so we can compute accurate
        # file-relative line numbers and preserve whitespace inside notes.
        content = match.group(1)
        # Line where the content block starts in the original file (1-indexed)
        base_line = text.count('\n', 0, match.start(1)) + 1
        lines = content.split('\n')  # preserve empty lines so numbering matches file

        session_data: Dict[str, Any] = {"exercises": []}
        # Keep a map of where top-level fields were parsed (absolute file line numbers)
        session_data['_line_numbers'] = {}
        current_exercise: Dict[str, Any] = {}
        multiline_key = None

        # Iterate with absolute line numbers to make errors traceable to the input file
        for rel_idx, raw_line in enumerate(lines):
            line_index = base_line + rel_idx
            line = raw_line.strip()
            # Check for main session keywords first
            if re.match(r"Date:", line, re.IGNORECASE):
                multiline_key = None
                session_data['date'] = line.split(':', 1)[1].strip()
                session_data['_line_numbers']['date'] = line_index
                continue
            if re.match(r"Phase:", line, re.IGNORECASE):
                multiline_key = None
                session_data['phase'] = int(line.split(':', 1)[1].strip())
                session_data['_line_numbers']['phase'] = line_index
                continue
            if re.match(r"Week:", line, re.IGNORECASE):
                multiline_key = None
                session_data['week'] = int(line.split(':', 1)[1].strip())
                session_data['_line_numbers']['week'] = line_index
                continue
            if re.match(r"Deload:", line, re.IGNORECASE):
                multiline_key = None
                session_data['is_deload_week'] = line.split(':', 1)[1].strip().lower() == 'yes'
                session_data['_line_numbers']['is_deload_week'] = line_index
                continue
            if re.match(r"Focus:", line, re.IGNORECASE):
                multiline_key = None
                session_data['focus'] = line.split(':', 1)[1].strip()
                session_data['_line_numbers']['focus'] = line_index
                continue
            # Accept both 'Duration:' and 'Session Duration:' (with optional whitespace)
            if re.match(r"(?:Session\s+)?Duration:", line, re.IGNORECASE):
                multiline_key = None
                duration_str = line.split(':', 1)[1].strip()
                session_data['session_duration_minutes'] = int(re.sub(r'\s*min', '', duration_str, flags=re.IGNORECASE))
                session_data['_line_numbers']['session_duration_minutes'] = line_index
                continue

            # Check for a new exercise
            # Allow optional whitespace between 'EX'/'Exercise' and the number (e.g., 'Ex 2:' or 'Exercise2:')
            ex_match = re.match(r"(?:EX|Exercise)\s*(\d+):\s*(.+)", line, re.IGNORECASE)
            if ex_match:
                multiline_key = None
                if current_exercise:
                    session_data["exercises"].append(current_exercise)
                current_exercise = {
                    "number": int(ex_match.group(1)),
                    "name": ex_match.group(2).strip(),
                    "warmup_sets": [],
                    "working_sets": [],
                    "line_number": line_index
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
                if not current_exercise:
                    logger.error("Found warmup set but no current exercise has been started. Line %s: %r", line_index, line)
                    raise ValueError(f"Warmup set encountered before any Exercise header (line {line_index}). Ensure 'ExerciseX:' appears before warmup sets.")
                # Defensive: ensure warmup_sets exists (some malformed blocks may have other keys but miss these)
                if "warmup_sets" not in current_exercise:
                    logger.warning("current_exercise missing 'warmup_sets'; creating empty list. exercise keys: %s (line %s)", list(current_exercise.keys()), line_index)
                    current_exercise.setdefault("warmup_sets", [])
                current_exercise["warmup_sets"].append(warmup_set)
                continue

            # Working Sets (this is the most complex one)
            set_match = re.match(r"(?:S|Set)(\d+):", line, re.IGNORECASE)
            if set_match:
                multiline_key = None
                set_num = int(set_match.group(1))
                remainder = line.split(":", 1)[1].strip()
                
                working_set = self._parse_working_set(set_num, remainder, line_index)
                if not current_exercise:
                    logger.error("Found working set but no current exercise has been started. Line %s: %r", line_index, line)
                    raise ValueError(f"Working set encountered before any Exercise header (line {line_index}). Ensure 'ExerciseX:' appears before working sets.")
                if "working_sets" not in current_exercise:
                    logger.warning("current_exercise missing 'working_sets'; creating empty list. exercise keys: %s (line %s)", list(current_exercise.keys()), line_index)
                    current_exercise.setdefault("working_sets", [])
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

    def _parse_working_set(self, set_num: int, line_part: str, line_index: int) -> Dict[str, Any]:
        """Helper to parse the complex working set line."""
        # Preserve the original raw fragment for logging and context
        original_fragment = line_part

        # Normalize spacing but do not mutate the original fragment. This
        # collapses multiple spaces and ensures there's a space around 'x'
        norm = re.sub(r"\s*x\s*", " x ", line_part, flags=re.IGNORECASE)
        norm = re.sub(r"\s+", " ", norm).strip()

        parts = norm.split()
        set_data: Dict[str, Any] = {"number": set_num}

        # Strategy A: tokens like [weight, 'x', reps(+partial)] -> common
        remaining_parts = ""
        if len(parts) >= 3 and parts[1].lower() == 'x':
            weight_token = parts[0]
            reps_token = parts[2]
            try:
                weight_val = float(weight_token)
            except Exception:
                logger.debug("Weight token not a float: %r (line %s)", weight_token, line_index)
                weight_val = None

            if weight_val is not None:
                # parse reps and optional partials
                if '+' in reps_token:
                    try:
                        full_str, part_str = reps_token.split('+', 1)
                        full_reps = int(full_str)
                        partial_reps = int(part_str)
                    except Exception:
                        logger.exception("Invalid reps token with plus at line %s: %r", line_index, reps_token)
                        raise ValueError(f"Invalid reps token for set {set_num} at line {line_index}: {reps_token}")
                else:
                    try:
                        full_reps = int(reps_token)
                        partial_reps = 0
                    except Exception:
                        logger.exception("Invalid reps token at line %s: %r", line_index, reps_token)
                        raise ValueError(f"Invalid reps token for set {set_num} at line {line_index}: {reps_token}")

                set_data["weight_kg"] = weight_val
                set_data["rep_count"] = {"full": full_reps, "partial": partial_reps}
                remaining_parts = " ".join(parts[3:])
            else:
                # Fall through to strategy B below
                remaining_parts = " ".join(parts[1:])
        else:
            # Strategy B: try a combined regex on the normalized line
            weight_rep_match = re.match(r"([\d.]+)\s*x\s*(\d+)(?:\+(\d+))?", norm, re.IGNORECASE)
            if weight_rep_match:
                weight, full_reps, partial_reps = weight_rep_match.groups()
                set_data["weight_kg"] = float(weight)
                set_data["rep_count"] = {"full": int(full_reps), "partial": int(partial_reps) if partial_reps else 0}
                # remove the matched portion from the normalized line to parse the rest
                remaining_parts = norm[weight_rep_match.end():].strip()
            else:
                # Log full context to help locate the bad input (use original fragment)
                logger.error("Could not parse weight/reps for set %s at line %s. norm_first_tokens=%r full_line=%r", set_num, line_index, parts[:3], original_fragment)
                raise ValueError(f"Could not parse weight/reps for set {set_num} at line {line_index}: {original_fragment}")
        
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