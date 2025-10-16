#!/usr/bin/env python3
import json
import re
import sys
from datetime import datetime

def parse_rep_object(rep_str):
    """Parses '10' or '10+2' into a dictionary."""
    if not rep_str:
        return {"full": None, "partial": 0}
    parts = [p.strip() for p in rep_str.split('+')]
    full_reps = int(parts[0]) if parts[0].isdigit() else None
    partial_reps = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return {"full": full_reps, "partial": partial_reps}

def parse_failure_technique(failure_str):
    """Parses 'myo(3,3,2)' or 'llp(6)' into a structured dictionary."""
    if not failure_str:
        return None
    
    match = re.match(r'(\w+)\((.*)\)', failure_str.strip())
    if not match:
        return None
        
    technique_type, details_str = match.groups()
    technique_type = technique_type.lower()
    details = {}

    if technique_type == 'myo':
        reps = [int(r.strip()) for r in details_str.split(',')]
        details['miniSets'] = [{"miniSet": i+1, "reps": r} for i, r in enumerate(reps)]
    elif technique_type == 'llp':
        details['partialReps'] = int(details_str)
    elif technique_type == 'static':
        details['durationMinutes'] = float(details_str)
    else: # Fallback for other types
        details['value'] = details_str
        
    return {"type": technique_type, "details": details}

def parse_goal(goal_str):
    """Parses '30kg x 3 sets x 6-8 reps' into a dictionary."""
    if not goal_str: return None
    match = re.search(r'(\d+\.?\d*)\s*kg\s*x\s*(\d+)\s*sets\s*x\s*(\d+)-(\d+)\s*reps', goal_str, re.IGNORECASE)
    if match:
        weight, sets, min_reps, max_reps = match.groups()
        return {
            "weightKg": float(weight),
            "sets": int(sets),
            "repRange": {"min": int(min_reps), "max": int(max_reps)}
        }
    return None

def parse_workout_log(file_path):
    """Main function to parse the text log file into a JSON structure."""
    with open(file_path, 'r') as f:
        content = f.read()

    sections = content.split('########################')
    sections = [s.strip() for s in sections if s.strip()]

    # Parse Session Metadata
    session_meta_text = sections[0]
    session_data = {}
    for line in session_meta_text.split('\n'):
        if ':' in line:
            key, val = [p.strip() for p in line.split(':', 1)]
            key = key.lower().replace(' ', '_')
            session_data[key] = val if val.lower() != 'null' else None
    
    # --- Interactive Validation for Session ---
    if not session_data.get('date'):
        session_data['date'] = input("⚠️ Date not found. Please enter date (YYYY-MM-DD): ").strip()
    if not session_data.get('duration'):
        duration_input = input("ℹ️ Session Duration not found. Enter duration in minutes (or press Enter to skip): ").strip()
        session_data['duration'] = duration_input if duration_input else None

    # Process final session data
    final_session_data = {
        "_id": f"training_session_{session_data.get('date', 'unknown')}",
        "userId": "your_user_id",
        "date": f"{session_data.get('date')}T00:00:00Z", # Assuming start of day if no time
        "phase": int(session_data.get('phase', 0)),
        "week": int(session_data.get('week', 0)),
        "isDeloadWeek": session_data.get('deload', 'no').lower() in ['yes', 'true'],
        "focus": session_data.get('focus'),
        "sessionDurationMinutes": int(session_data['duration']) if session_data.get('duration', '').isdigit() else None,
        "exercises": []
    }
    
    # Parse Exercises
    exercise_texts = sections[1:]
    for i, text in enumerate(exercise_texts):
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        exercise_data = {"sequence": i + 1, "warmupSets": [], "workingSets": [], "formCues": []}
        
        # State machine for multi-line parsing
        current_section = None 
        
        for line in lines:
            line_lower = line.lower()
            
            if line_lower.startswith('ex '):
                exercise_data['exerciseName'] = line.split(':', 1)[1].strip()
                current_section = None
            elif line_lower.startswith('goal:'):
                goal_obj = parse_goal(line.split(':', 1)[1].strip())
                if goal_obj:
                    exercise_data['goal'] = goal_obj
                current_section = None
            elif line_lower.startswith('rest:'):
                rest_val = line.split(':', 1)[1].strip()
                if 'min' in rest_val and exercise_data.get('goal'):
                    exercise_data['goal']['restMinutes'] = float(re.findall(r"(\d+\.?\d*)", rest_val)[0])
                current_section = None
            elif line_lower.startswith('warmup notes:'):
                exercise_data['warmupNotes'] = line.split(':', 1)[1].strip()
                current_section = 'warmup_notes'
            elif line_lower.startswith('notes:'):
                exercise_data['notes'] = line.split(':', 1)[1].strip()
                current_section = 'notes'
            elif line_lower.startswith('cues:'):
                cues_text = line.split(':', 1)[1].strip()
                if cues_text: exercise_data['formCues'].append(cues_text)
                current_section = 'cues'
            elif line_lower.startswith('w'):
                match = re.match(r'w(\d+):\s*([\d\.]+\s*x\s*[\w\-]+)(.*)', line, re.IGNORECASE)
                if match:
                    set_num, performance, notes = match.groups()
                    weight_str, rep_str = [p.strip() for p in performance.split('x')]
                    reps_val = int(rep_str) if rep_str.isdigit() else None
                    set_notes = notes.replace('-', '').strip()
                    if rep_str.lower() == 'feel':
                        set_notes = "Reps performed by feel. " + set_notes
                    exercise_data['warmupSets'].append({
                        "set": int(set_num), "weightKg": float(weight_str), "reps": reps_val, "notes": set_notes.strip()
                    })
                current_section = None
            elif line_lower.startswith('s'):
                match = re.match(r'(\([\d\.]+\s*m\))?\s*s(\d+):\s*([\d\.]+\s*x\s*[\d\+]+)\s*RPE\s*(\d+)\s*(\w+)\s*(-.*)?', line, re.IGNORECASE)
                if match:
                    rest, set_num, performance, rpe, quality, notes_failure = match.groups()
                    actual_rest = float(rest.strip('()m')) if rest else None
                    weight_str, rep_str = [p.strip() for p in performance.split('x')]
                    notes = ""
                    failure_technique = None
                    if notes_failure:
                        notes_failure = notes_failure.lstrip('- ').strip()
                        if notes_failure.lower().startswith('f:'):
                            failure_technique = parse_failure_technique(notes_failure.split(':', 1)[1].strip())
                        else:
                            notes = notes_failure
                            
                    exercise_data['workingSets'].append({
                        "set": int(set_num), "weightKg": float(weight_str), "reps": parse_rep_object(rep_str),
                        "rpe": int(rpe), "repQuality": quality.lower(), "actualRestMinutes": actual_rest,
                        "notes": notes if notes else None, "failureTechnique": failure_technique
                    })
                current_section = None
            elif current_section == 'cues':
                exercise_data['formCues'].append(line)
            elif current_section == 'notes' and 'notes' in exercise_data:
                exercise_data['notes'] += ' ' + line
            elif current_section == 'warmup_notes' and 'warmupNotes' in exercise_data:
                exercise_data['warmupNotes'] += ' ' + line


        final_session_data['exercises'].append(exercise_data)
        
    return final_session_data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parser.py <path_to_log_file.txt>")
        sys.exit(1)
        
    input_file = sys.argv[1]
    output_file = input_file.replace('.txt', '.json')

    try:
        parsed_data = parse_workout_log(input_file)
        
        with open(output_file, 'w') as f:
            json.dump(parsed_data, f, indent=2)
            
        print("\n✅ SUCCESS: Parsing complete.")
        print(f"📄 Input file:  {input_file}")
        print(f"💾 Output JSON saved to: {output_file}")
        
    except FileNotFoundError:
        print(f"❌ ERROR: The file '{input_file}' was not found.")
    except Exception as e:
        print(f"❌ ERROR: An unexpected error occurred during parsing: {e}")