"""
Migration management without Alembic.

Simple version-based migration strategy with manual SQL steps documented in docs/development/MIGRATIONS.md
"""

from persistence.database import Database
from typing import Optional


class MigrationManager:
    """Manages schema migrations with simple version tracking."""

    # Current schema version
    CURRENT_VERSION = 1

    def __init__(self, db: Database):
        """
        Initialize migration manager.
        
        Args:
            db: Database instance
        """
        self.db = db

    def get_version(self) -> int:
        """
        Get current schema version from database.
        
        Returns:
            Current schema version
        """
        try:
            cursor = self.db.execute("SELECT version FROM schema_version ORDER BY rowid DESC LIMIT 1")
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    def check_schema_compatibility(self) -> bool:
        """
        Check if current schema version matches expected version.
        
        Returns:
            True if versions match, False otherwise
        """
        current = self.get_version()
        if current != self.CURRENT_VERSION:
            print(f"⚠️  Schema version mismatch!")
            print(f"   Database version: {current}")
            print(f"   Expected version: {self.CURRENT_VERSION}")
            print(f"   Please consult docs/development/MIGRATIONS.md for upgrade steps.")
            return False
        return True

    def upgrade_to(self, target_version: int):
        """
        Upgrade schema to target version.
        
        Args:
            target_version: Target schema version
            
        Raises:
            NotImplementedError: If migration path not defined
        """
        current = self.get_version()
        
        if current == target_version:
            print(f"✓ Schema already at version {target_version}")
            return
        
        if current > target_version:
            raise ValueError(f"Cannot downgrade from {current} to {target_version}")
        
        # Add migration paths here as needed
        # Example: if current == 1 and target_version == 2:
        #     self._migrate_v1_to_v2()
        
        raise NotImplementedError(
            f"Migration path from v{current} to v{target_version} not implemented"
        )

    def _update_schema_version(self, version: int):
        """
        Update schema version in database.
        
        Args:
            version: New schema version
        """
        try:
            self.db.execute("DELETE FROM schema_version")
            self.db.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to update schema version: {e}")
