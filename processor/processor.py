# main.py
import json
import logging
import sys
from pathlib import Path

# When this file is executed directly (e.g. `python3 processor.py` from
# the `processor/` directory) Python's import system may not find the
# sibling top-level packages (like `parser` and `datamodels`). Ensure
# the project root is on sys.path so absolute imports like
# `from parser.parser import ...` work regardless of the current CWD.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.parser import WorkoutParser
from parser.ingester import DataIngestor

# Configure a basic logger for CLI usage. Callers (tests) can override this
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Define constants for input and output directories
INPUT_DIR = Path("workout_logs_raw")
OUTPUT_DIR = Path("workout_log_json")

def main():
    """
    Main function to run the workout log processing pipeline.
    It reads all .txt files from an input directory, processes them,
    and saves them with dynamic names to an output directory.
    """
    # 1. Ensure directories exist
    if not INPUT_DIR.is_dir():
        print(f"❌ Error: Input directory not found at '{INPUT_DIR}'")
        print("Please create it and add your workout .txt files.")
        return

    # Create the output directory if it doesn't exist
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 2. Find all workout log files to process
    workout_files = list(INPUT_DIR.glob("*.txt"))
    if not workout_files:
        print(f"🤷 No workout files (.txt) found in '{INPUT_DIR}'.")
        return

    print(f"Found {len(workout_files)} log file(s) to process...")

    # Initialize the parser and ingestor once
    parser = WorkoutParser()
    ingestor = DataIngestor()

    # 3. Process each file
    for file_path in workout_files:
        print(f"\n--- Processing '{file_path.name}' ---")
        try:
            raw_text = file_path.read_text(encoding='utf-8')

            # Parse the raw text into a dictionary
            parsed_data = parser.parse(raw_text)
            if not parsed_data:
                print(f"⚠️ Skipping '{file_path.name}': Could not find BEGIN/END blocks.")
                continue

            # Ingest the dictionary into dataclass objects
            training_session = ingestor.ingest(parsed_data)

            # Generate the dynamic output filename
            # Replace spaces in 'focus' with hyphens for a cleaner filename
            focus_sanitized = training_session.focus.replace(" ", "-").lower()
            output_filename = f"{focus_sanitized}_{training_session.date}.json"
            output_path = OUTPUT_DIR / output_filename

            # Convert the final dataclass object to a JSON-compatible dictionary
            final_dict = training_session.to_dict()

            # Write the final JSON to the output file
            output_path.write_text(json.dumps(final_dict, indent=2), encoding='utf-8')
            
            print(f"✅ Success! Output saved to '{output_path}'")

        except Exception:
            # Log full stack trace and continue with next file
            logger.exception("❌ An unexpected error occurred while processing '%s'", file_path.name)

if __name__ == "__main__":
    main()