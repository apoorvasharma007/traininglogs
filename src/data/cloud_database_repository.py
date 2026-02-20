"""Optional cloud database repository for persistent remote backup."""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple


class CloudDatabaseRepository(ABC):
    """Abstract cloud persistence adapter."""

    mode: str = "disabled"

    @abstractmethod
    def save_session(self, session_id: str, session_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Persist session to cloud backend."""


class DisabledCloudDatabaseRepository(CloudDatabaseRepository):
    """No-op cloud repository used when cloud is not configured."""

    mode = "disabled"

    def save_session(self, session_id: str, session_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        return False, None


class UnavailableCloudDatabaseRepository(CloudDatabaseRepository):
    """Configured cloud repository that cannot run due to missing dependency."""

    mode = "unavailable"

    def __init__(self, reason: str):
        self.reason = reason

    def save_session(self, session_id: str, session_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        return False, self.reason


class PostgresCloudDatabaseRepository(CloudDatabaseRepository):
    """Cloud repository backed by Postgres (psycopg)."""

    mode = "postgres"

    def __init__(self, dsn: str):
        self.dsn = dsn

    def save_session(self, session_id: str, session_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        try:
            import psycopg
        except ImportError:
            return False, "psycopg is not installed. Install with: pip install psycopg[binary]"

        try:
            with psycopg.connect(self.dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS training_sessions (
                            id TEXT PRIMARY KEY,
                            date TEXT,
                            phase TEXT,
                            week INTEGER,
                            raw_json JSONB,
                            created_at TEXT
                        )
                        """
                    )
                    cur.execute(
                        """
                        INSERT INTO training_sessions
                        (id, date, phase, week, raw_json, created_at)
                        VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (id)
                        DO UPDATE SET
                            date = EXCLUDED.date,
                            phase = EXCLUDED.phase,
                            week = EXCLUDED.week,
                            raw_json = EXCLUDED.raw_json,
                            created_at = EXCLUDED.created_at
                        """,
                        (
                            session_id,
                            session_data.get("date"),
                            session_data.get("phase"),
                            session_data.get("week"),
                            json.dumps(session_data),
                            session_data.get("created_at"),
                        ),
                    )
            return True, None
        except Exception as err:
            return False, str(err)


def build_cloud_database_repository() -> CloudDatabaseRepository:
    """
    Build cloud repository from environment.

    Env:
      TRAININGLOGS_CLOUD_POSTGRES_DSN=postgres://...
    """
    dsn = os.getenv("TRAININGLOGS_CLOUD_POSTGRES_DSN")
    if not dsn:
        return DisabledCloudDatabaseRepository()

    try:
        import psycopg  # noqa: F401
    except ImportError:
        return UnavailableCloudDatabaseRepository(
            "Cloud DSN configured but psycopg is missing. Install with: pip install psycopg[binary]"
        )

    return PostgresCloudDatabaseRepository(dsn)

