"""Service for metadata intake parsing, validation, and mapping."""

from typing import Any, Dict, Tuple

from contracts.metadata_contracts import SessionMetadataContract, default_session_metadata
from core.validators import ValidationError
from intake.input_parsing_service import InputParsingService
from intake.validate_data_service import ValidateDataService


class MetadataService:
    """Owns metadata defaults, updates, and contract mapping."""

    def __init__(
        self,
        parsing_service: InputParsingService,
        validation_service: ValidateDataService,
    ):
        self.parsing = parsing_service
        self.validation = validation_service

    @staticmethod
    def default_metadata() -> Dict[str, Any]:
        return default_session_metadata()

    def preview_and_apply_update(
        self,
        raw: str,
        current: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """Parse one metadata update and return preview + candidate metadata."""
        parsed = self.parsing.parse_metadata_update(raw, current)
        if not parsed:
            raise ValidationError(
                "I couldn't parse metadata from that message. "
                "Use explicit values (for example: 'phase 2 week 7 focus upper-strength no deload') "
                "or enable LLM mode with TRAININGLOGS_LLM_ENABLED=true."
            )

        updates = parsed.payload.get("updates", {})
        if not updates:
            raise ValidationError("No metadata fields detected in that message.")

        candidate = dict(current)
        candidate.update(updates)
        self.validation.validate_metadata(candidate)

        return parsed.preview or "Metadata update detected.", candidate

    def to_contract(self, metadata: Dict[str, Any]) -> SessionMetadataContract:
        """Convert validated metadata dict to canonical contract."""
        self.validation.validate_metadata(metadata)
        return SessionMetadataContract(
            phase=metadata["phase"],
            week=int(metadata["week"]),
            focus=metadata["focus"],
            is_deload=bool(metadata["is_deload"]),
            date=metadata.get("date"),
        )
