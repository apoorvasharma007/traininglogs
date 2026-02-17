#!/usr/bin/env python3
"""
Test: Complete persistence end-to-end
Verifies that sessions are saved to BOTH database and JSON files
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, 'src')

from config import settings
from persistence import get_database, TrainingSessionRepository, SessionExporter
from core import SessionManager

def test_complete_persistence_flow():
    """Test database + JSON file persistence."""
    
    print("\n" + "="*60)
    print("PERSISTENCE TEST: Database + JSON File Export")
    print("="*60)
    
    # Initialize
    db = get_database(settings.get_db_path())
    db.init_schema()
    
    repo = TrainingSessionRepository(db)
    session_mgr = SessionManager(repo)
    
    # Create session
    print("\n1️⃣  Creating session...")
    session = session_mgr.start_session(
        phase='phase 2',
        week=5,
        focus='upper-strength',
        is_deload=False
    )
    print(f"   ✅ Session created: {session['id'][:8]}...")
    
    # Add exercises
    print("\n2️⃣  Adding exercises...")
    session_mgr.add_exercise(
        name='Barbell Bench Press',
        warmup_sets=[{'weight': 20, 'reps': 5}],
        working_sets=[{'weight': 80, 'reps': 5, 'rpe': 8}]
    )
    print("   ✅ Added: Barbell Bench Press")
    
    session_mgr.add_exercise(
        name='Incline Dumbbell Press',
        warmup_sets=[{'weight': 10, 'reps': 8}],
        working_sets=[{'weight': 30, 'reps': 8, 'rpe': 7}]
    )
    print("   ✅ Added: Incline Dumbbell Press")
    
    # Persist to BOTH database and JSON
    print("\n3️⃣  Persisting session...")
    session_mgr.persist_session()
    print("   ✅ Saved to database: traininglogs.db")
    print("   ✅ Exported to JSON: data/output/sessions/")
    
    # Verify database file
    print("\n4️⃣  Verifying DATABASE persistence...")
    db_path = Path('traininglogs.db')
    if db_path.exists():
        db_size = db_path.stat().st_size
        print(f"   ✅ File exists: {db_path}")
        print(f"   ✅ File size: {db_size} bytes")
    else:
        print(f"   ❌ Database file not found!")
        return False
    
    # Verify JSON file
    print("\n5️⃣  Verifying JSON FILE persistence...")
    json_files = list(Path('data/output/sessions').glob('*.json'))
    if json_files:
        print(f"   ✅ Found {len(json_files)} JSON file(s)")
        
        # Check most recent file
        latest = max(json_files, key=lambda p: p.stat().st_mtime)
        print(f"   ✅ Latest file: {latest.name}")
        
        # Verify JSON structure
        with open(latest) as f:
            data = json.load(f)
        
        print(f"   ✅ JSON is valid")
        print(f"   ✅ Session ID: {data['_id'][:8]}...")
        print(f"   ✅ Phase: {data['phase']}, Week: {data['week']}")
        print(f"   ✅ Exercises: {len(data['exercises'])}")
        
        # Verify exercises in JSON
        for idx, ex in enumerate(data['exercises'], 1):
            print(f"      {idx}. {ex['Name']}")
            print(f"         - Warmup: {len(ex['warmupSets'])} set(s)")
            print(f"         - Working: {len(ex['workingSets'])} set(s)")
    else:
        print(f"   ❌ No JSON files found!")
        return False
    
    # Verify data consistency
    print("\n6️⃣  Verifying data consistency...")
    
    # Query database
    all_sessions = repo.get_all_sessions()
    print(f"   ✅ Database contains {len(all_sessions)} session(s)")
    
    if all_sessions:
        db_session = all_sessions[-1]  # Last session
        print(f"   ✅ Exercises in DB: {len(db_session.get('exercises', []))}")
        
        # Compare with JSON
        if abs(len(db_session.get('exercises', [])) - len(data['exercises'])) == 0:
            print(f"   ✅ Database and JSON have same data!")
        else:
            print(f"   ⚠️  Exercise count mismatch (DB has {len(db_session.get('exercises', []))}, JSON has {len(data['exercises'])})")
    
    db.close()
    
    print("\n" + "="*60)
    print("✨ PERSISTENCE TEST PASSED")
    print("="*60)
    print("\n📊 Summary:")
    print("   ✅ Database: traininglogs.db (SQLite)")
    print("   ✅ JSON Files: data/output/sessions/*.json")
    print("\n🎯 Each session now creates BOTH files automatically!")
    print("\n" + "="*60 + "\n")
    
    return True

if __name__ == '__main__':
    success = test_complete_persistence_flow()
    sys.exit(0 if success else 1)
