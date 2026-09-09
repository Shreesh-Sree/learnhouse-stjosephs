"""Unified Bi-Directional AI Guardrail Service."""

import logging
from typing import Any, AsyncGenerator, Optional

from src.services.ai.guardrails.input_guard import validate_input
from src.services.ai.guardrails.output_guard import guardrail_stream, validate_output
from src.services.ai.guardrails.system_defense import inject_system_guardrail
from src.services.ai.guardrails.types import (
    GuardrailResult,
    GuardrailVerdict,
    GuardrailViolationType,
)

logger = logging.getLogger(__name__)


def apply_input_guardrail(
    prompt: Any,
    history: Optional[Any] = None,
    strict: bool = True,
) -> GuardrailResult:
    """Validate user prompt before invoking any LLM across the platform."""
    return validate_input(prompt, history=history, strict=strict)


def apply_output_guardrail(
    text: str,
    original_prompt: str = "",
) -> GuardrailResult:
    """Validate and sanitize model output before returning to caller."""
    return validate_output(text, original_prompt=original_prompt)


def wrap_output_stream(
    stream_generator: AsyncGenerator[str, None],
    original_prompt: str = "",
) -> AsyncGenerator[str, None]:
    """Wrap a chunk stream with the streaming output guardrail filter."""
    return guardrail_stream(stream_generator, original_prompt=original_prompt)


def harden_system_prompt(base_system_prompt: Optional[str]) -> str:
    """Inject the immutable educational guardrail contract into system prompts."""
    return inject_system_guardrail(base_system_prompt)
