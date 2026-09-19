from unittest.mock import AsyncMock

import pytest

from app.providers.gemini import GeminiProvider
from app.schemas.llm import LLMMessage, LLMMessageRole, LLMRequest, LLMStreamChunk
from app.schemas.tool import ToolDefinition


class FakeUsage:
    prompt_token_count = 123
    candidates_token_count = 45


class FakeChunk:
    def __init__(self, text=None, usage=False):
        self.text = text
        self.usage_metadata = FakeUsage() if usage else None


@pytest.mark.asyncio
async def test_gemini_stream_returns_typed_chunks_and_usage():
    provider = GeminiProvider(api_key="test", default_model="gemini", timeout=30)

    async def fake_stream():
        yield FakeChunk(text="Hello")
        yield FakeChunk(text=" world", usage=True)

    provider._client.aio.models.generate_content_stream = AsyncMock(
        return_value=fake_stream()
    )

    request = LLMRequest(messages=[LLMMessage(role=LLMMessageRole.USER, content="Hi")])

    result = [chunk async for chunk in provider.generate_stream(request)]

    assert all(isinstance(chunk, LLMStreamChunk) for chunk in result)
    assert [chunk.content for chunk in result] == ["Hello", " world"]
    assert result[-1].usage is not None
    assert result[-1].usage.input_tokens == 123
    assert result[-1].usage.output_tokens == 45


@pytest.mark.asyncio
async def test_gemini_stream_passes_tools_and_system_instruction():
    provider = GeminiProvider(api_key="test", default_model="gemini", timeout=30)

    async def fake_stream():
        yield FakeChunk(text="ok")

    provider._client.aio.models.generate_content_stream = AsyncMock(
        return_value=fake_stream()
    )

    tool = ToolDefinition(
        name="validate",
        description="Validate a value",
        parameters={"type": "object"},
    )
    request = LLMRequest(
        messages=[
            LLMMessage(role=LLMMessageRole.SYSTEM, content="Be concise"),
            LLMMessage(role=LLMMessageRole.USER, content="Hi"),
        ],
        tools=[tool],
    )

    result = [chunk async for chunk in provider.generate_stream(request)]

    assert result[0].content == "ok"
    call = provider._client.aio.models.generate_content_stream.call_args
    config = call.kwargs["config"]
    assert config is not None
    assert config.tools
    assert config.system_instruction == ["Be concise"]
