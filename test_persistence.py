#!/usr/bin/env python3
"""Test persistence with file export."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config import settings
from persistence import get_database, TrainingSessionRepository
from core import SessionManager

def test_persistence():
    """Test database and file persistence."""
    # Initialize
    db = get_database(settings.get_db_path())
    db.init_schema()
    
    # Create session manager
    repo = TrainingSessionRepository(db)
    session_mgr = SessionManager(repo)
    
    # Start session
    session = session_mgr.start_session(
        phase='phase 2',
        week=5,
        focus='upper-strength',
        is_deload=False
    )
    
    # Add exercise
    session_mgr.add_exercise(
        name='Barbell Bench Press',
        warmup_sets=[{'weight': 20, 'reps': 5}],
        working_sets=[{'weight': 80, 'reps': 5, 'rpe': 8}]
    )
    
    # Persist (DB + JSON file)
    session_mgr.persist_session()
    
    print('✅ Session persisted successfully!')
    print(f'   Session ID: {session["id"][:8]}')
    
    # Verify files
    db_exists = Path('traininglogs.db').exists()
    json_files = list(Path('data/output/sessions').glob('*.json'))
    
    print(f'\n📊 Persistence Status:')
    print(f'   ✅ Database: traininglogs.db ({db_exists})')
    print(f'   ✅ JSON files: {len(json_files)} file(s)')
    if json_files:
        for f in json_files:
            size = f.stat().st_size
            print(f'      - {f.name} ({size} bytes)')
    
    # Show JSON content
    if json_files:
        print(f'\n📄 Sample JSON file content:')
        with open(json_files[0]) as f:
            import json
            data = json.load(f)
            print(f'   ID: {data.get("_id")}')
            print(f'   Phase: {data.get("phase")}, Week: {data.get("week")}')
            print(f'   Focus: {data.get("focus")}')
            print(f'   Exercises: {len(data.get("exercises", []))}')
            if data.get("exercises"):
                ex = data["exercises"][0]
                print(f'   First exercise: {ex.get("Name")}')
    
    db.close()
    return 0

if __name__ == "__main__":
    sys.exit(test_persistence())
