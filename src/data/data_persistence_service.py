"""Orchestrate local/cloud/json writes and live-session recovery state."""

from typing import Any, Dict, Optional

from contracts.session_contracts import PersistenceOutcomeContract


class DataPersistenceService:
    """Single persistence entry point for workflow layer."""

    def __init__(
        self,
        database_repository,
        json_export_service,
        live_session_store,
        cloud_repository,
    ):
        self.local_db = database_repository
        self.json_export = json_export_service
        self.live_store = live_session_store
        self.cloud_db = cloud_repository

    def begin_session(self, session_dict: Dict[str, Any]) -> None:
        self.live_store.begin_session(session_dict)

    def append_event(self, session_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        self.live_store.append_event(session_id, event_type, payload)

    def update_snapshot(self, session_dict: Dict[str, Any], current_exercise: Optional[Dict[str, Any]]) -> None:
        self.live_store.update_snapshot(session_dict, current_exercise=current_exercise)

    def close_session(self, session_dict: Dict[str, Any], status: str) -> None:
        self.live_store.close_session(session_dict, status=status)

    def get_latest_resumable_snapshot(self):
        return self.live_store.get_latest_resumable_snapshot()

    def persist_final_session(
        self,
        session_id: str,
        session_dict: Dict[str, Any],
        save_requested: bool,
    ) -> PersistenceOutcomeContract:
        """Persist session and return a fully structured outcome."""
        if not save_requested:
            self.close_session(session_dict, status="not_saved")
            return PersistenceOutcomeContract(
                saved_local=False,
                saved_json=False,
                saved_cloud=False,
                status="not_saved",
                cloud_mode=self.cloud_db.mode,
            )

        # Local DB write is mandatory.
        try:
            self.local_db.save_session(session_id, session_dict)
        except Exception as err:
            self.close_session(session_dict, status="save_failed_local")
            return PersistenceOutcomeContract(
                saved_local=False,
                saved_json=False,
                saved_cloud=False,
                status="save_failed_local",
                local_error=str(err),
                cloud_mode=self.cloud_db.mode,
            )

        saved_json = False
        json_error = None
        try:
            self.json_export.export_session(session_dict)
            saved_json = True
        except Exception as err:
            json_error = str(err)

        saved_cloud = False
        cloud_error = None
        if self.cloud_db.mode != "disabled":
            saved_cloud, cloud_error = self.cloud_db.save_session(session_id, session_dict)

        status = "saved"
        if not saved_json and self.cloud_db.mode == "disabled":
            status = "saved_local_only"
        elif not saved_json and not saved_cloud:
            status = "saved_with_warnings"

        self.close_session(session_dict, status=status)
        return PersistenceOutcomeContract(
            saved_local=True,
            saved_json=saved_json,
            saved_cloud=saved_cloud,
            status=status,
            json_error=json_error,
            cloud_error=cloud_error,
            cloud_mode=self.cloud_db.mode,
        )

