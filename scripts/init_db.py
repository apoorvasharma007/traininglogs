#!/usr/bin/env python3
"""
Initialize training logs database.

Creates SQLite database and schema.
Usage: python scripts/init_db.py
"""

import argparse
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import settings
from persistence import Database, MigrationManager


def main():
    """Initialize database."""
    # Use configured path from settings
    db_path = settings.get_db_path()
    
    print(f"📦 Initializing database at: {db_path}")
    
    try:
        # Ensure directory exists
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create database and initialize schema
        db = Database(db_path)
        db.init_schema()
        print("✓ Database schema created/verified")
        
        # Check migration status
        migration_manager = MigrationManager(db)
        version = migration_manager.get_version()
        print(f"✓ Schema version: {version}")
        
        # Verify compatibility
        if migration_manager.check_schema_compatibility():
            print("✓ Schema is compatible")
        
        db.close()
        print("\n✓ Database initialization complete!")
        print(f"   Database file: {db_path}")
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
