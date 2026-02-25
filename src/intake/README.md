# intake

## Purpose
Input parsing, normalization, and validation for metadata/exercise intake.

## Main Modules
- `input_parsing_service.py`: command + LLM intent parsing.
- `metadata_service.py`: metadata update flow and mapping.
- `exercise_entry_service.py`: draft exercise mutations and commit prep.
- `validate_data_service.py`: strict normalization and validation.

## Boundary
- Converts user-provided inputs into valid structured payloads.
