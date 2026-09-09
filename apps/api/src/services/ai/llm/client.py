"""Unified, provider-neutral generation helpers.

All AI text generation in the backend goes through ``generate`` / ``generate_stream`` so the
underlying provider is a config concern, not a code concern. These wrap Pydantic AI's
``Agent`` and translate the app's stored message/attachment formats into Pydantic AI types.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, AsyncGenerator, Optional, Sequence, Type, Union

from pydantic_ai import Agent
from pydantic_ai.messages import (
    BinaryContent,
    DocumentUrl,
    ImageUrl,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
    VideoUrl,
)
from pydantic_ai.settings import ModelSettings

from src.services.ai.llm.provider import build_model

logger = logging.getLogger(__name__)

# Per-request timeouts (seconds). Generous defaults to prevent premature mid-response cutoffs.
DEFAULT_TIMEOUT = 180.0
STREAM_TIMEOUT = 300.0

# A single user turn: a prompt string plus optional multimodal parts (images/docs/video).
UserPrompt = Union[str, Sequence[Any]]


def to_message_history(stored: Any) -> list[ModelMessage]:
    """Convert stored chat history into Pydantic AI ``ModelMessage`` objects.

    Accepts the Redis JSON format (``[{"role": "user"|"model", "content": str}, ...]``) and
    the legacy object format (``msg.type``/``msg.content``). Unknown entries are skipped.
    """
    messages: list[ModelMessage] = []
    if not stored:
        return messages

    items = getattr(stored, "messages", stored)
    for msg in items:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            role, content = msg["role"], msg["content"]
        elif hasattr(msg, "type") and hasattr(msg, "content"):
            role = "user" if msg.type == "human" else "model"
            content = msg.content
        else:
            continue

        if not content:
            continue
        if role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        else:
            messages.append(ModelResponse(parts=[TextPart(content=content)]))
    return messages


def attachments_to_parts(attachments: Any) -> list:
    """Convert ``AttachmentData``-like objects into Pydantic AI multimodal parts.

    Replaces the Gemini-specific ``inline_data``/``file_data`` dicts. Note: video/YouTube and
    URL-based documents are only honored by providers that support them (e.g. Gemini); other
    providers will ignore or reject them — an inherent provider capability difference.
    """
    parts: list = []
    for att in attachments or []:
        a_type = getattr(att, "type", None)
        url = getattr(att, "url", None)
        b64 = getattr(att, "content_base64", None)
        mime = getattr(att, "mime_type", None)

        if a_type == "youtube" and url:
            parts.append(VideoUrl(url=url))
        elif a_type in ("image", "file") and b64 and mime:
            # content_base64 is user-supplied; a malformed/truncated value would
            # raise binascii.Error and surface as an unhandled 500. Skip the bad
            # attachment instead of crashing the whole request.
            try:
                decoded = base64.b64decode(b64)
            except Exception:
                logger.warning("Skipping attachment with invalid base64 content")
                continue
            parts.append(BinaryContent(data=decoded, media_type=mime))
        elif a_type == "image" and url:
            parts.append(ImageUrl(url=url))
        elif a_type == "file" and url:
            parts.append(DocumentUrl(url=url))
    return parts


def _settings(
    max_tokens: Optional[int], temperature: Optional[float], timeout: float
) -> ModelSettings:
    settings: dict = {"timeout": timeout}
    if max_tokens is not None:
        settings["max_tokens"] = max_tokens
    else:
        # Default generous headroom ceiling (4096 tokens) so long / multilingual responses never cut off
        settings["max_tokens"] = 4096
    if temperature is not None:
        settings["temperature"] = temperature
    return ModelSettings(**settings)


from src.services.ai.guardrails import (
    apply_input_guardrail,
    apply_output_guardrail,
    harden_system_prompt,
    wrap_output_stream,
)


def _agent(
    model_name: str,
    system_prompt: Optional[str],
    output_type: Any,
    tools: Optional[Sequence[Any]] = None,
) -> Agent:
    return Agent(
        build_model(model_name),
        output_type=output_type,
        system_prompt=system_prompt or (),
        tools=list(tools) if tools else [],
    )


async def generate(
    *,
    model_name: str,
    user_prompt: UserPrompt,
    system_prompt: Optional[str] = None,
    history: Any = None,
    output_type: Type[Any] = str,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    timeout: float = DEFAULT_TIMEOUT,
    tools: Optional[Sequence[Any]] = None,
) -> Any:
    """Run a single (non-streaming) generation with bi-directional guardrails.

    Returns plain text when ``output_type`` is ``str``, or a validated instance of
    ``output_type`` (a Pydantic model) for structured output. ``tools`` are plain
    type-annotated async functions the model may call mid-run (e.g. web search) —
    see src/services/ai/tools/. Omit for the previous, tool-free behavior.
    """
    # 1. Inbound Guardrail
    guard_in = apply_input_guardrail(user_prompt, history=history)
    if not guard_in.passed:
        if output_type is str:
            return guard_in.refusal_message
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=guard_in.refusal_message)

    # 2. System Prompt Defense
    hardened_system_prompt = harden_system_prompt(system_prompt)

    agent = _agent(model_name, hardened_system_prompt, output_type, tools)
    result = await agent.run(
        user_prompt,
        message_history=to_message_history(history) or None,
        model_settings=_settings(max_tokens, temperature, timeout),
    )

    # 3. Outbound Guardrail
    if isinstance(result.output, str):
        guard_out = apply_output_guardrail(result.output, original_prompt=str(user_prompt))
        if not guard_out.passed:
            return guard_out.refusal_message
        return guard_out.sanitized_text

    return result.output


async def generate_stream(
    *,
    model_name: str,
    user_prompt: UserPrompt,
    system_prompt: Optional[str] = None,
    history: Any = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    timeout: float = STREAM_TIMEOUT,
    tools: Optional[Sequence[Any]] = None,
) -> AsyncGenerator[str, None]:
    """Stream text deltas for a single generation with bi-directional guardrails.

    Yields chunks as they arrive through the outbound guardrail filter.
    """
    # 1. Inbound Guardrail
    guard_in = apply_input_guardrail(user_prompt, history=history)
    if not guard_in.passed:
        yield guard_in.refusal_message
        return

    # 2. System Prompt Defense
    hardened_system_prompt = harden_system_prompt(system_prompt)

    agent = _agent(model_name, hardened_system_prompt, str, tools)

    async def _raw_stream() -> AsyncGenerator[str, None]:
        async with agent.run_stream(
            user_prompt,
            message_history=to_message_history(history) or None,
            model_settings=_settings(max_tokens, temperature, timeout),
        ) as result:
            async for chunk in result.stream_text(delta=True):
                yield chunk

    # 3. Outbound Streaming Guardrail
    async for sanitized_chunk in wrap_output_stream(_raw_stream(), original_prompt=str(user_prompt)):
        yield sanitized_chunk
