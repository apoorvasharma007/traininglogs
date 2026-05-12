from __future__ import annotations

from collections.abc import Callable

from traininglogs.agent.llm_extract_validator import LLMExtractValidator
from traininglogs.agent.llm_parser import (
    ExtractionProvider,
    TrainingLogLLMExtract,
    parse,
)
from traininglogs.agent.renderer import TerminalRenderer
from traininglogs.agent.validation_card_builder import ValidationCardBuilder

_CONFIRM_PROMPT = (
    "\n[bold]Confirm?[/bold] [dim]Enter 'y' to accept, or describe a correction:[/dim] "
)


class LLMOrchestrator:
    def __init__(
        self,
        parser_provider: ExtractionProvider | None = None,
        correction_provider: ExtractionProvider | None = None,
        renderer: TerminalRenderer | None = None,
        input_fn: Callable[[], str] = input,
    ) -> None:
        self._parser_provider = parser_provider
        self._correction_provider = correction_provider
        self._renderer = renderer or TerminalRenderer()
        self._input_fn = input_fn
        self._builder = ValidationCardBuilder()

    def run(self, text: str) -> TrainingLogLLMExtract:
        from traininglogs.agent.llm_parser import AnthropicProvider

        parser_provider = self._parser_provider or AnthropicProvider()
        correction_provider = self._correction_provider or parser_provider
        validator = LLMExtractValidator(correction_provider)

        extract = parse(text, provider=parser_provider)

        while True:
            card = self._builder.build(extract)
            self._renderer.render(card)
            self._renderer.console.print(_CONFIRM_PROMPT, end="")
            answer = self._input_fn().strip()
            if answer.lower() in {"y", "yes"}:
                return extract
            if answer:
                extract = validator.apply_correction(extract, answer)
