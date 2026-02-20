"""
Live session autosave for in-progress workout logging.

Writes:
- append-only event log (.jsonl)
- latest recoverable snapshot (.snapshot.json)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List


class LiveSessionStore:
    """Persist in-progress sessions for recovery and audit."""

    def __init__(self, output_dir: str = "data/output/live_sessions"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def begin_session(self, session_dict: Dict[str, Any]) -> None:
        """Create initial snapshot and start event."""
        session_id = session_dict["id"]
        self.append_event(session_id, "session_started", {"session": session_dict})
        self.update_snapshot(session_dict, current_exercise=None, status="in_progress")

    def append_event(self, session_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        """Append one event to jsonl event stream."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": event_type,
            "payload": payload,
        }
        with open(self._events_path(session_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def update_snapshot(
        self,
        session_dict: Dict[str, Any],
        current_exercise: Optional[Dict[str, Any]],
        status: str = "in_progress",
    ) -> None:
        """Write current recoverable state atomically."""
        snapshot = {
            "updated_at": datetime.now().isoformat(),
            "status": status,
            "session": session_dict,
            "current_exercise": current_exercise,
        }

        target = self._snapshot_path(session_dict["id"])
        tmp = target.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        tmp.replace(target)

    def close_session(self, session_dict: Dict[str, Any], status: str) -> None:
        """
        Mark session as completed/cancelled/not_saved.

        The snapshot is intentionally preserved to allow post-session inspection.
        """
        session_id = session_dict["id"]
        self.append_event(
            session_id,
            "session_closed",
            {
                "status": status,
                "exercise_count": len(session_dict.get("exercises", [])),
            },
        )
        self.update_snapshot(session_dict, current_exercise=None, status=status)

    def load_snapshot(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load one session snapshot by session id."""
        path = self._snapshot_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all readable snapshots sorted by updated_at descending."""
        snapshots: List[Dict[str, Any]] = []
        for file_path in self.output_dir.glob("*.snapshot.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                snapshots.append(data)
            except json.JSONDecodeError:
                continue

        snapshots.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return snapshots

    def get_latest_resumable_snapshot(self) -> Optional[Dict[str, Any]]:
        """
        Return latest snapshot that can be resumed.

        Resumable statuses:
        - in_progress
        - not_saved
        """
        resumable = {"in_progress", "not_saved"}
        for snapshot in self.list_snapshots():
            if snapshot.get("status") in resumable:
                return snapshot
        return None

    def _events_path(self, session_id: str) -> Path:
        return self.output_dir / f"{session_id}.events.jsonl"

    def _snapshot_path(self, session_id: str) -> Path:
        return self.output_dir / f"{session_id}.snapshot.json"
