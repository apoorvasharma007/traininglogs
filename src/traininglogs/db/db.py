"""Connecting, and bringing a database's schema up to date.

The schema is the numbered files in migrations/ (0001_baseline.sql, then 0002_..., and so on).
Each runs once per database, in number order, and the table schema_migrations records it with a
checksum of its text. A file that has run anywhere is never edited: a change goes in a new file."""
import hashlib
import os
import re
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as Connection

MIGRATIONS = Path(__file__).parent / "migrations"
# Any fixed number. Two runs at the same time take turns on it instead of both running a file.
_LOCK_ID = 20261025


def get_connection(database_url: str | None = None) -> Connection:
    url = database_url or os.environ["DATABASE_URL"]
    return psycopg2.connect(url)


def migration_files(folder: Path = MIGRATIONS) -> list[tuple[int, Path]]:
    files = []
    for path in sorted(folder.glob("*.sql")):
        match = re.fullmatch(r"(\d{4})_[a-z0-9_]+\.sql", path.name)
        if match is None:
            raise ValueError(f"{path.name}: name it NNNN_what_it_does.sql")
        files.append((int(match[1]), path))
    numbers = [number for number, _ in files]
    if len(set(numbers)) != len(numbers):
        raise ValueError(f"two files in {folder} share a number")
    return files


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pending_migrations(conn: Connection, folder: Path = MIGRATIONS) -> list[Path]:
    """The files this database hasn't run, in order. Writes nothing, so it's safe on production.
    Refuses when a file that already ran here has changed since."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('schema_migrations') IS NOT NULL")
        done: dict[int, str] = {}
        if cur.fetchone()[0]:
            cur.execute("SELECT version, checksum FROM schema_migrations")
            done = dict(cur.fetchall())
    pending = []
    for number, path in migration_files(folder):
        if number not in done:
            pending.append(path)
        elif done[number] != _checksum(path):
            raise RuntimeError(
                f"{path.name} changed after it ran on this database. Undo the edit and put the change in a new file."
            )
    return pending


def apply_schema(conn: Connection, commit: bool = True, folder: Path = MIGRATIONS) -> list[str]:
    """Runs the files this database hasn't run, all in one transaction, and returns their names.
    `commit=False` leaves it in the caller's transaction (the accounts migration)."""
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_ID,))
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    INT PRIMARY KEY,
                name       TEXT NOT NULL,
                checksum   TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY;
            """
        )
    applied = []
    for path in pending_migrations(conn, folder):
        with conn.cursor() as cur:
            cur.execute(path.read_text())
            cur.execute(
                "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                (int(path.name[:4]), path.name, _checksum(path)),
            )
        applied.append(path.name)
    if commit:
        conn.commit()
    return applied
