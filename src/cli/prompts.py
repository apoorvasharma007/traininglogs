"""
Interactive prompts for traininglogs CLI.

Helper functions for user input and display.
"""

from typing import Optional, List

from .mobile_commands import COMMAND_HELP


def _parse_yes_no(choice: str) -> Optional[bool]:
    """Normalize common yes/no replies."""
    lowered = (choice or "").strip().lower()
    if lowered in {"y", "yes"}:
        return True
    if lowered in {"n", "no"}:
        return False
    return None


def prompt_session_metadata() -> dict:
    """
    Prompt user for training session metadata.
    
    Returns:
        Dictionary with session metadata
    """
    print("\n🏋️  Starting new training session")
    print("=" * 50)

    # Date (skip for now, defaults to today)
    print("\nℹ️  Session date will default to today")
    
    # Phase
    phase = input("\nPhase (phase 1, phase 2, phase 3): ").strip()
    
    # Week
    while True:
        try:
            week = int(input("Week number: ").strip())
            if week < 1:
                print("❌ Week must be 1 or greater")
                continue
            break
        except ValueError:
            print("❌ Please enter a valid number")

    # Focus
    focus = input("Workout focus (e.g., upper-strength, legs-hypertrophy): ").strip()

    # Deload week
    is_deload = input("Is this a deload week? (y/n): ").strip().lower() == 'y'

    return {
        "phase": phase,
        "week": week,
        "focus": focus,
        "is_deload": is_deload
    }


def prompt_exercise_name(exercise_number: int) -> str:
    """
    Prompt user for exercise name.
    
    Args:
        exercise_number: Exercise number in session
        
    Returns:
        Exercise name
    """
    return input(f"\nExercise #{exercise_number} name: ").strip()


def prompt_continue_session() -> str:
    """
    Prompt user to continue adding exercises.
    
    Returns:
        User choice: 'y' to add more, 'n' to finish, 't' to finalize and save
    """
    choice = input("\n(a)dd exercise, (f)inish session, (c)ancel? [a/f/c]: ").strip().lower()
    return choice


def confirm_save() -> bool:
    """
    Confirm before saving session.
    
    Returns:
        True if user confirms save
    """
    while True:
        choice = input("\n✓ Save session? (y/n): ")
        parsed = _parse_yes_no(choice)
        if parsed is not None:
            return parsed
        print("Please enter y/yes or n/no.")


def show_session_summary(session: dict):
    """
    Display session summary before saving.
    
    Args:
        session: Session dictionary
    """
    print("\n📊 Session Summary")
    print("=" * 50)
    print(f"Phase: {session.get('phase', 'N/A')}")
    print(f"Week: {session.get('week', 'N/A')}")
    print(f"Focus: {session.get('focus', 'N/A')}")
    print(f"Deload: {'Yes' if session.get('is_deload') else 'No'}")
    print(f"Exercises: {len(session.get('exercises', []))}")
    
    for exercise in session.get('exercises', []):
        working_sets = exercise.get('working_sets', [])
        print(f"  - {exercise['name']}: {len(working_sets)} working sets")


def show_error(message: str):
    """Display error message."""
    print(f"\n❌ Error: {message}")


def show_success(message: str):
    """Display success message."""
    print(f"\n✓ {message}")


def show_info(message: str):
    """Display info message."""
    print(f"\nℹ️  {message}")


def show_mobile_help():
    """Display mobile command grammar."""
    print(COMMAND_HELP)


def prompt_mobile_command() -> str:
    """
    Prompt one command line for mobile mode.

    Returns:
        Raw user input line
    """
    return input("\ncmd> ").strip()


# NEW FUNCTIONS FOR REFACTORED AGENT-BASED CLI

def show_exercise_context(context):
    """
    Display exercise context with history and suggestions.
    
    Args:
        context: LoggingContext from agent
    """
    print(f"\n📋 Logging: {context.exercise_name}")
    print("=" * 50)
    
    if context.is_new_exercise:
        print("✨ New exercise - no history to reference")
    else:
        if context.last_weight:
            days = f"{context.days_since_last} days ago" if context.days_since_last else "recently"
            print(f"📚 Last: {context.last_weight}kg (logged {days})")
        
        if context.max_weight:
            print(f"⭐ Max ever: {context.max_weight}kg")
        
        if context.suggested_weight:
            print(f"💡 Suggested: {context.suggested_weight}kg")
        
        if context.suggested_reps_range:
            print(f"   Rep range: {context.suggested_reps_range[0]}-{context.suggested_reps_range[1]} reps")


def prompt_sets(
    set_type: str,
    suggested_count: int = 1,
    suggested_weight: float = None,
    suggested_reps_range: tuple = None
) -> list:
    """
    Prompt user for exercise sets with smart defaults.
    
    Args:
        set_type: "warmup" or "working"
        suggested_count: Default number of sets
        suggested_weight: AI-suggested weight
        suggested_reps_range: AI-suggested rep range (min, max)
        
    Returns:
        List of sets [{'weight': X, 'reps': Y, 'rpe': Z}, ...]
    """
    sets = []
    set_type_label = "Warmup" if set_type == "warmup" else "Working"
    
    print(f"\n{set_type_label.upper()} SETS")
    print("-" * 40)
    
    # Ask for number of sets
    num_sets_input = input(f"Number of {set_type} sets? [{suggested_count}]: ").strip()
    num_sets = int(num_sets_input) if num_sets_input else suggested_count
    
    for i in range(1, num_sets + 1):
        print(f"\n{set_type_label} Set #{i}")
        
        # Weight
        weight_prompt = f"  Weight (kg)"
        if suggested_weight:
            weight_prompt += f" [{suggested_weight}]"
        weight_prompt += ": "
        weight_input = input(weight_prompt).strip()
        weight = float(weight_input) if weight_input else suggested_weight
        
        if weight is None:
            print("  ❌ Weight required")
            i -= 1  # Repeat this set
            continue
        
        # Reps
        reps_hint = ""
        if suggested_reps_range:
            reps_hint = f" [{suggested_reps_range[0]}-{suggested_reps_range[1]}]"
        reps_input = input(f"  Reps{reps_hint}: ").strip()
        reps = int(reps_input) if reps_input else None
        
        if reps is None:
            print("  ❌ Reps required")
            i -= 1  # Repeat this set
            continue
        
        # RPE (optional for warmups, important for working)
        rpe_input = input(f"  RPE (1-10) [skip if warmup]: ").strip()
        rpe = int(rpe_input) if rpe_input else None
        
        set_data = {
            "weight": weight,
            "reps": reps
        }
        if rpe is not None:
            set_data["rpe"] = rpe
        
        sets.append(set_data)
    
    return sets


def confirm_action(action_text: str) -> bool:
    """
    Ask user to confirm an action.
    
    Args:
        action_text: Description of action
        
    Returns:
        True if confirmed
    """
    while True:
        choice = input(f"\n{action_text} (y/n): ")
        parsed = _parse_yes_no(choice)
        if parsed is not None:
            return parsed
        print("Please enter y/yes or n/no.")
