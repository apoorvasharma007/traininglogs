import os
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as Connection


def get_connection(database_url: str | None = None) -> Connection:
    url = database_url or os.environ["DATABASE_URL"]
    return psycopg2.connect(url)


def apply_schema(conn: Connection) -> None:
    db_dir = Path(__file__).parent
    with conn.cursor() as cur:
        cur.execute((db_dir / "schema.sql").read_text())
    conn.commit()
