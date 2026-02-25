"""Hybrid data source that merges DB sessions with JSON exports."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from repository.data_source import DataSource


class HybridDataSource(DataSource):
    """Read/query sessions from DB + JSON with normalized shapes."""

    def __init__(self, db_repo, json_dir: str = "data/output/sessions"):
        self.db = db_repo
        self.json_dir = Path(json_dir)

    def get_last_exercise(self, exercise_name: str) -> Optional[Dict[str, Any]]:
        name = exercise_name.strip().lower()
        if not name:
            return None
        for session in self._iter_sessions():
            for exercise in self._iter_exercises(session):
                if exercise.get("name", "").lower() == name:
                    return exercise
        return None

    def get_exercise_history(
        self,
        exercise_name: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent occurrences of an exercise."""
        history: List[Dict[str, Any]] = []
        name = exercise_name.strip().lower()
        if not name or limit <= 0:
            return history
        for session in self._iter_sessions():
            for exercise in self._iter_exercises(session):
                if exercise.get("name", "").lower() == name:
                    history.append(exercise)
                    if len(history) >= limit:
                        return history
        return history

    def get_sessions(
        self,
        phase: Optional[str] = None,
        week: Optional[int] = None,
        focus: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Query sessions with optional filters."""
        sessions: List[Dict[str, Any]] = []
        if limit <= 0:
            return sessions
        for session in self._iter_sessions():
            if self._matches_filters(session, phase, week, focus):
                sessions.append(session)
                if len(sessions) >= limit:
                    break
        return sessions

    def save_session(self, session_data: Dict[str, Any]) -> bool:
        """Save session via DB repository."""
        session_id = session_data.get("id")
        return bool(self.db.save_session(session_id, session_data))

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve specific session."""
        for session in self._iter_sessions():
            if session.get("id") == session_id:
                return session
        return None

    def search_exercises(
        self,
        pattern: str,
        limit: int = 5,
    ) -> List[str]:
        """Search for exercises by name pattern."""
        exercises_found = set()
        if limit <= 0:
            return []
        p = pattern.strip().lower()
        if not p:
            return []
        for session in self._iter_sessions():
            for exercise in self._iter_exercises(session):
                name = exercise.get("name", "")
                if p in name.lower():
                    exercises_found.add(name)
                    if len(exercises_found) >= limit:
                        return sorted(list(exercises_found))
        return sorted(list(exercises_found))

    # Helper methods

    def _normalize_exercise(self, exercise: Dict[str, Any], session_date: Optional[str]) -> Dict[str, Any]:
        """Normalize exercise shape from different storage formats."""
        warmup_sets = exercise.get("warmup_sets", exercise.get("warmupSets", []))
        working_sets = exercise.get("working_sets", exercise.get("workingSets", []))
        return {
            "name": exercise.get("name", exercise.get("Name")),
            "warmup_sets": [self._normalize_set(s) for s in warmup_sets],
            "working_sets": [self._normalize_set(s) for s in working_sets],
            "session_date": session_date,
        }

    def _normalize_set(self, set_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize set shape from schema and runtime forms."""
        rep_count = set_data.get("repCount")
        if isinstance(rep_count, dict):
            reps = rep_count.get("full", 0) + rep_count.get("partial", 0)
        elif isinstance(rep_count, int):
            reps = rep_count
        else:
            reps = set_data.get("reps")

        normalized = {
            "weight": set_data.get("weight", set_data.get("weightKg")),
            "reps": reps,
        }
        if set_data.get("rpe") is not None:
            normalized["rpe"] = set_data.get("rpe")
        return normalized

    def _normalize_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize session shape from db/json records."""
        phase = session.get("phase")
        if isinstance(phase, int):
            phase = f"phase {phase}"
        return {
            "id": session.get("id", session.get("_id")),
            "date": session.get("date"),
            "phase": phase,
            "week": session.get("week"),
            "focus": session.get("focus"),
            "is_deload": session.get("is_deload", session.get("isDeloadWeek", False)),
            "exercises": [
                self._normalize_exercise(exercise, session.get("date"))
                for exercise in session.get("exercises", [])
            ],
            "created_at": session.get("created_at"),
        }

    def _parse_timestamp(self, value: Optional[str]) -> datetime:
        """Parse timestamp consistently for deterministic sorting."""
        if not value:
            return datetime.min
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.min

    def _iter_sessions(self) -> List[Dict[str, Any]]:
        """Return canonical deduplicated sessions sorted newest-first."""
        db_sessions = [self._normalize_session(s) for s in self.db.get_all_sessions()]
        json_sessions = [self._normalize_session(s) for s in self._get_sessions_from_json()]

        merged = {}
        ordered = []
        for session in db_sessions + json_sessions:
            session_id = session.get("id")
            dedupe_key = session_id or f"json:{session.get('date')}:{len(ordered)}"
            if dedupe_key in merged:
                continue
            merged[dedupe_key] = session
            ordered.append(session)

        ordered.sort(
            key=lambda s: (
                self._parse_timestamp(s.get("date")),
                self._parse_timestamp(s.get("created_at")),
                s.get("id") or "",
            ),
            reverse=True,
        )
        return ordered

    def _iter_exercises(self, session: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Yield canonical exercises from a normalized session."""
        return session.get("exercises", [])

    def _matches_filters(
        self,
        session: Dict[str, Any],
        phase: Optional[str],
        week: Optional[int],
        focus: Optional[str],
    ) -> bool:
        """Check if session matches filters."""
        if phase and session.get("phase") != phase:
            return False
        if week is not None and session.get("week") != week:
            return False
        if focus and session.get("focus") != focus:
            return False
        return True

    def _get_sessions_from_json(self) -> List[Dict[str, Any]]:
        """Read all sessions from JSON directory."""
        sessions: List[Dict[str, Any]] = []
        if not self.json_dir.exists():
            return sessions

        for json_file in sorted(self.json_dir.glob("*.json"), reverse=True):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append(data)
            except json.JSONDecodeError:
                continue

        return sessions
