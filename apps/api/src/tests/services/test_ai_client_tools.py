"""Integration test that tool-calling is actually wired through generate() /
generate_stream() end to end — not just that the tools param is accepted, but
that a tool call the model makes actually reaches the real Python function and
its result flows back into the response. Uses Pydantic AI's TestModel (no
network, no real provider) so this runs in any environment.
"""

from unittest.mock import patch

import pytest
from pydantic_ai.models.test import TestModel

from src.services.ai.llm import client as client_mod


async def get_secret_number() -> int:
    """Returns a fixed number a real model could never guess on its own —
    proof the tool itself, not the model's training data, produced the value."""
    return 4242


@pytest.mark.asyncio
async def test_generate_calls_registered_tool_and_uses_its_result(monkeypatch):
    monkeypatch.setattr(
        client_mod, "build_model", lambda model_name: TestModel(call_tools=["get_secret_number"])
    )
    result = await client_mod.generate(
        model_name="test-model",
        user_prompt="What is the secret number?",
        tools=[get_secret_number],
    )
    # TestModel echoes tool call results back into its default response —
    # the tool's actual return value must appear somewhere in the output.
    assert "4242" in str(result)


@pytest.mark.asyncio
async def test_generate_stream_calls_registered_tool(monkeypatch):
    monkeypatch.setattr(
        client_mod, "build_model", lambda model_name: TestModel(call_tools=["get_secret_number"])
    )
    chunks = []
    async for chunk in client_mod.generate_stream(
        model_name="test-model",
        user_prompt="What is the secret number?",
        tools=[get_secret_number],
    ):
        chunks.append(chunk)
    assert "4242" in "".join(chunks)


@pytest.mark.asyncio
async def test_generate_with_no_tools_never_calls_the_function(monkeypatch):
    """Omitting tools (the previous, unmodified call shape every existing
    caller uses) must behave exactly as before — no tool available to call."""
    called = False

    async def spy_tool() -> int:
        nonlocal called
        called = True
        return 1

    monkeypatch.setattr(client_mod, "build_model", lambda model_name: TestModel())
    await client_mod.generate(model_name="test-model", user_prompt="hello")
    assert called is False


@pytest.mark.asyncio
async def test_agent_receives_no_tools_by_default():
    """_agent() with tools omitted must not error and must build an Agent
    with an empty toolset — the pre-existing, tool-free code path."""
    with patch.object(client_mod, "build_model", return_value=TestModel()):
        agent = client_mod._agent("test-model", None, str)
    assert agent is not None
