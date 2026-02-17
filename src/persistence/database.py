"""
Database connection and schema management.

Provides SQLite connection handling and schema initialization.
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional


class Database:
    """Manages SQLite database connection and lifecycle."""

    def __init__(self, db_path: str = "traininglogs.db"):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. Defaults to traininglogs.db in root.
        """
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """
        Establish database connection.
        
        Returns:
            sqlite3.Connection object
        """
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
        return self.connection

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a query.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            sqlite3.Cursor object
        """
        conn = self.connect()
        return conn.execute(query, params)

    def commit(self):
        """Commit current transaction."""
        if self.connection:
            self.connection.commit()

    def rollback(self):
        """Rollback current transaction."""
        if self.connection:
            self.connection.rollback()

    def init_schema(self):
        """Initialize database schema."""
        conn = self.connect()
        cursor = conn.cursor()

        # Schema version tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        """)

        # Training sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_sessions (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                phase TEXT,
                week INTEGER,
                raw_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Create indices
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_training_date 
            ON training_sessions(date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_training_phase 
            ON training_sessions(phase)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_training_week 
            ON training_sessions(week)
        """)

        # Initialize schema version if not exists
        cursor.execute("SELECT COUNT(*) FROM schema_version")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO schema_version (version) VALUES (1)")

        conn.commit()


def get_database(db_path: Optional[str] = None) -> Database:
    """
    Factory function to get database instance.
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        Database instance
    """
    if db_path is None:
        # Look for .env or use default
        db_path = os.getenv("TRAININGLOGS_DB", "traininglogs.db")
    
    return Database(db_path)
