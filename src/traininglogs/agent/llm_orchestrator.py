from __future__ import annotations

import os
from collections.abc import Callable

from traininglogs.agent.extraction import assemble, parse
from traininglogs.agent.llm_extract_validator import LLMExtractValidator
from traininglogs.agent.providers import ExtractionProvider
from traininglogs.agent.renderer import TerminalRenderer
from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.agent.validation_card_builder import ValidationCardBuilder

_CONFIRM_PROMPT = (
    "\n[bold]Confirm?[/bold] [dim]Enter 'y' to accept, or describe a correction:[/dim] "
)

# Escape hatch back to the monolithic single-call parse() for comparison against the
# split-call assemble() path (the default). Set to "1" to use the old path without touching
# calling code — same purpose as the constructor's use_monolithic_parser argument.
USE_MONOLITHIC_PARSER_ENV_VAR = "TRAININGLOGS_USE_MONOLITHIC_PARSER"


class LLMOrchestrator:
    def __init__(
        self,
        parser_provider: ExtractionProvider | None = None,
        correction_provider: ExtractionProvider | None = None,
        renderer: TerminalRenderer | None = None,
        input_fn: Callable[[], str] = input,
        use_monolithic_parser: bool | None = None,
    ) -> None:
        self._parser_provider = parser_provider
        self._correction_provider = correction_provider
        self._renderer = renderer or TerminalRenderer()
        self._input_fn = input_fn
        self._builder = ValidationCardBuilder()
        if use_monolithic_parser is None:
            use_monolithic_parser = os.environ.get(USE_MONOLITHIC_PARSER_ENV_VAR) == "1"
        self._use_monolithic_parser = use_monolithic_parser

    def run(self, text: str) -> TrainingLogLLMExtract:
        """Extract, show the card, apply corrections until confirmed.

        Every correction is recorded in `self.corrections` -- what the person said, and the
        edits it produced. The caller stores that alongside the extraction, which keeps three
        facts permanently separable: what the model read, what the person changed, and what was
        stored. It also turns "which fields do I correct most often?" into a query, which is a
        prompt-improvement backlog generated from real use rather than guesswork.

        Deliberately no database access here. The orchestrator drives a conversation; the
        caller owns storage.
        """
        from datetime import datetime, timezone

        from traininglogs.agent.providers import AnthropicProvider

        self.corrections: list[dict] = []
        # The model's own reading, before any human correction. Kept so the three facts stay
        # separable forever: what the model said, what the person changed, what was stored.
        self.original_extract: TrainingLogLLMExtract | None = None

        parser_provider = self._parser_provider or AnthropicProvider()
        correction_provider = self._correction_provider or parser_provider
        validator = LLMExtractValidator(correction_provider)

        if self._use_monolithic_parser:
            extract = parse(text, provider=parser_provider)
        else:
            extract = assemble(text, provider=parser_provider)

        self.original_extract = extract

        while True:
            card = self._builder.build(extract)
            self._renderer.render(card)
            self._renderer.console.print(_CONFIRM_PROMPT, end="")
            answer = self._input_fn().strip()
            if answer.lower() in {"y", "yes"}:
                return extract
            if answer:
                extract, edits = validator.apply_correction(extract, answer)
                self.corrections.append(
                    {
                        "at": datetime.now(timezone.utc).isoformat(),
                        "instruction": answer,
                        "edits": [e.model_dump(mode="json") for e in edits],
                    }
                )
