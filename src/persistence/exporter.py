"""
Session data exporter to JSON files.

Exports training sessions as JSON files matching the schema structure.
Ensures permanent, readable output files for every session logged.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import uuid4


class SessionExporter:
    """Exports training sessions to JSON files matching schema."""

    def __init__(self, output_dir: str = "data/output/sessions"):
        """
        Initialize exporter.
        
        Args:
            output_dir: Directory to write session files to
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_session(self, session_data: Dict[str, Any]) -> str:
        """
        Export session to JSON file.
        
        Args:
            session_data: Session dictionary from SessionManager
            
        Returns:
            Path to written file
            
        Raises:
            Exception: On file write error
        """
        try:
            # Transform session data to schema format
            schema_data = self._transform_to_schema(session_data)
            
            # Generate filename
            session_date = session_data.get("date", datetime.now().isoformat())
            filename = self._generate_filename(session_date, session_data.get("id"))
            
            # Write file
            file_path = self.output_dir / filename
            with open(file_path, 'w') as f:
                json.dump(schema_data, f, indent=2)
            
            return str(file_path)
            
        except Exception as e:
            raise Exception(f"Failed to export session: {e}")

    def _transform_to_schema(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform session data to match schema structure.
        
        Args:
            session_data: Raw session data
            
        Returns:
            Schema-compliant dictionary
        """
        # Parse date
        date_str = session_data.get("date", datetime.now().isoformat())
        try:
            session_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            session_date = datetime.now()
        
        # Transform exercises
        exercises = []
        for idx, exercise in enumerate(session_data.get("exercises", []), 1):
            exercises.append(self._transform_exercise(exercise, idx))
        
        # Build schema
        schema = {
            "dataModelVersion": "0.0.1",
            "dataModelType": "training_session_log",
            "_id": session_data.get("id", str(uuid4())),
            "userId": "apoorva",
            "userName": "Apoorva Sharma",
            "date": session_date.isoformat(),
            "phase": int(session_data.get("phase", "2").replace("phase ", "")),
            "week": session_data.get("week", 1),
            "isDeloadWeek": session_data.get("is_deload", False),
            "focus": session_data.get("focus", "General"),
            "exercises": exercises
        }
        
        return schema

    def _transform_exercise(self, exercise: Dict[str, Any], order: int) -> Dict[str, Any]:
        """
        Transform exercise data to schema format.
        
        Args:
            exercise: Exercise dictionary
            order: Exercise order in session
            
        Returns:
            Schema-compliant exercise dictionary
        """
        return {
            "Order": order,
            "Name": exercise.get("name", "Unknown"),
            "targetMuscleGroups": exercise.get("target_muscle_groups", []),
            "repTempo": exercise.get("rep_tempo"),
            "currentGoal": exercise.get("goal", {}),
            "warmupSets": self._transform_sets(exercise.get("warmup_sets", []), "warmup"),
            "workingSets": self._transform_sets(exercise.get("working_sets", []), "working")
        }

    def _transform_sets(self, sets: list, set_type: str) -> list:
        """
        Transform set data to schema format.
        
        Args:
            sets: List of set dictionaries
            set_type: Type of sets ("warmup" or "working")
            
        Returns:
            Transformed sets list
        """
        transformed = []
        
        for idx, set_data in enumerate(sets, 1):
            if set_type == "warmup":
                transformed.append({
                    "set": idx,
                    "weightKg": set_data.get("weight"),
                    "repCount": set_data.get("reps"),
                    "notes": set_data.get("notes")
                })
            else:  # working set
                transformed.append({
                    "set": idx,
                    "weightKg": set_data.get("weight"),
                    "repCount": {
                        "full": set_data.get("reps", 0),
                        "partial": 0
                    },
                    "rpe": set_data.get("rpe"),
                    "repAssessment": "perfect",
                    "actualRestMinutes": set_data.get("rest_minutes"),
                    "notes": set_data.get("notes")
                })
        
        return transformed

    def _generate_filename(self, date_str: str, session_id: str) -> str:
        """
        Generate filename for session.
        
        Args:
            date_str: Session date (ISO format)
            session_id: Session ID
            
        Returns:
            Filename string
        """
        try:
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            date_part = date_obj.strftime("%Y_%m_%d")
        except:
            date_part = "unknown_date"
        
        # Use first 8 chars of session ID
        id_part = session_id[:8] if session_id else "noID"
        
        return f"training_session_{date_part}_{id_part}.json"
