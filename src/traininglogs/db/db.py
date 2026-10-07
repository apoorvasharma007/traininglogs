"""Database connection and schema management."""
import os
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as Connection


def get_connection(database_url: str | None = None) -> Connection:
    """Open a new database connection, using DATABASE_URL env var if not provided."""
    url = database_url or os.environ["DATABASE_URL"]
    return psycopg2.connect(url)


def apply_schema(conn: Connection, commit: bool = True) -> None:
    """Creates whatever schema.sql describes that doesn't exist yet. `commit=False` leaves it in
    the caller's transaction (the accounts migration)."""
    with conn.cursor() as cur:
        cur.execute((Path(__file__).parent / "schema.sql").read_text())
    if commit:
        conn.commit()
