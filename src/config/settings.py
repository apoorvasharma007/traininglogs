"""
Configuration and settings for traininglogs CLI.

Loads configuration from environment variables and defaults.
"""

import os
from pathlib import Path


class Settings:
    """Application settings."""

    # Paths - use absolute paths
    PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()  # Go up to project root
    DATA_DIR = PROJECT_ROOT / "data"
    DB_DIR = DATA_DIR / "database"
    OUTPUT_DIR = DATA_DIR / "output"
    SESSIONS_DIR = OUTPUT_DIR / "sessions"
    LOGS_DIR = OUTPUT_DIR / "logs"
    
    # Database
    DB_PATH: str = os.getenv("TRAININGLOGS_DB", str(DB_DIR / "traininglogs.db"))
    
    # CLI
    DEBUG: bool = os.getenv("TRAININGLOGS_DEBUG", "False").lower() == "true"
    
    # Legacy paths
    DOCS_DIR = PROJECT_ROOT / "docs"
    
    # Defaults
    DEFAULT_PHASE: str = "phase 2"
    PHASES: list = ["phase 1", "phase 2", "phase 3"]
    
    def __init__(self):
        """Initialize settings and create necessary directories."""
        self.ensure_directories()
    
    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        for directory in [self.DB_DIR, self.SESSIONS_DIR, self.LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_db_path(cls) -> str:
        """Get absolute path to database file."""
        db_path = cls.DB_PATH
        if not os.path.isabs(db_path):
            db_path = os.path.join(str(cls.PROJECT_ROOT), db_path)
        return db_path
    
    def get_output_dir(self) -> str:
        """Get the output directory path."""
        return str(self.OUTPUT_DIR)
    
    def get_sessions_dir(self) -> str:
        """Get the sessions output directory path."""
        return str(self.SESSIONS_DIR)


# Create singleton instance
settings = Settings()
