import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.exceptions.provider import LLMProviderError
from app.schemas.llm import LLMMessage, LLMMessageRole, LLMStreamChunk, LLMUsage
from app.services.conversation import ConversationOrchestratorService


@pytest.fixture
def orchestrator():
    service = ConversationOrchestratorService.__new__(ConversationOrchestratorService)

    service.provider = Mock()
    service.tool_registry = Mock()
    service.rate_limit_service = Mock()
    service.message_service = Mock()
    service.chat_service = Mock()
    service.context_builder = Mock()
    service.summary_service = Mock()

    return service


def make_context(messages=None, estimated_tokens=100):
    context = Mock()

    context.messages = messages or [
        LLMMessage(
            role=LLMMessageRole.USER,
            content="Hello",
        )
    ]

    context.estimated_tokens = estimated_tokens
    context.should_summarize = False
    context.omitted_messages = []

    return context


@pytest.mark.asyncio
async def test_stream_records_actual_provider_usage(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    context = make_context(
        estimated_tokens=100,
    )

    orchestrator._prepare_conversation = AsyncMock(return_value=context)

    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)

    orchestrator.tool_registry.definitions.return_value = []

    async def fake_stream(request):
        yield LLMStreamChunk(
            content="Hello ",
        )

        yield LLMStreamChunk(
            content="world",
        )

        yield LLMStreamChunk(
            content=None,
            usage=LLMUsage(
                input_tokens=120,
                output_tokens=25,
            ),
        )

    orchestrator._stream_with_retry = fake_stream

    orchestrator.message_service.create_assistant_message = AsyncMock()

    chunks = []

    async for chunk in orchestrator.stream_message(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    ):
        chunks.append(chunk)

    assert "data: Hello \n\n" in chunks
    assert "data: world\n\n" in chunks

    orchestrator.rate_limit_service.record_provider_usage.assert_called_once_with(
        user_id=user_id,
        input_tokens=120,
        output_tokens=25,
    )


@pytest.mark.asyncio
async def test_stream_uses_last_usage_chunk(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    context = make_context(
        estimated_tokens=100,
    )

    orchestrator._prepare_conversation = AsyncMock(return_value=context)

    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)

    orchestrator.tool_registry.definitions.return_value = []

    async def fake_stream(request):
        yield LLMStreamChunk(
            content="Hello",
            usage=None,
        )

        yield LLMStreamChunk(
            content=" world",
            usage=LLMUsage(
                input_tokens=200,
                output_tokens=40,
            ),
        )

        yield LLMStreamChunk(
            content=None,
            usage=LLMUsage(
                input_tokens=210,
                output_tokens=45,
            ),
        )

    orchestrator._stream_with_retry = fake_stream

    orchestrator.message_service.create_assistant_message = AsyncMock()

    async for _ in orchestrator.stream_message(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    ):
        pass

    orchestrator.rate_limit_service.record_provider_usage.assert_called_once_with(
        user_id=user_id,
        input_tokens=210,
        output_tokens=45,
    )


@pytest.mark.asyncio
async def test_stream_falls_back_to_estimated_usage(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    context = make_context(
        estimated_tokens=100,
    )

    orchestrator._prepare_conversation = AsyncMock(return_value=context)

    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)

    orchestrator.tool_registry.definitions.return_value = []

    async def fake_stream(request):
        yield LLMStreamChunk(content="Hello")
        yield LLMStreamChunk(content=" world")

    orchestrator._stream_with_retry = fake_stream

    orchestrator.message_service.create_assistant_message = AsyncMock()

    async for _ in orchestrator.stream_message(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    ):
        pass

    call = orchestrator.rate_limit_service.record_provider_usage.call_args

    assert call.kwargs["user_id"] == user_id
    assert call.kwargs["input_tokens"] == 100
    assert call.kwargs["output_tokens"] > 0


@pytest.mark.asyncio
async def test_stream_failure_does_not_record_provider_usage(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    context = make_context(
        estimated_tokens=100,
    )

    orchestrator._prepare_conversation = AsyncMock(return_value=context)

    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)

    async def fake_stream(request):
        yield LLMStreamChunk(
            content="partial",
        )

        raise LLMProviderError()

    orchestrator._stream_with_retry = fake_stream

    orchestrator.message_service.create_assistant_message = AsyncMock()

    chunks = []

    async for chunk in orchestrator.stream_message(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    ):
        chunks.append(chunk)

    orchestrator.rate_limit_service.record_provider_usage.assert_not_called()

    orchestrator.message_service.create_assistant_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_cancellation_does_not_record_usage(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    context = make_context(
        estimated_tokens=100,
    )

    orchestrator._prepare_conversation = AsyncMock(return_value=context)

    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)

    orchestrator.tool_registry.definitions.return_value = []

    async def fake_stream(request):
        yield LLMStreamChunk(content="Hello")
        raise asyncio.CancelledError()

    orchestrator._stream_with_retry = fake_stream

    with pytest.raises(asyncio.CancelledError):
        async for _ in orchestrator.stream_message(
            chat_id=chat_id,
            user_id=user_id,
            content="Hello",
        ):
            pass

    orchestrator.rate_limit_service.record_provider_usage.assert_not_called()


@pytest.mark.asyncio
async def test_stream_checks_cost_token_limit_before_provider_call(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    context = make_context(
        estimated_tokens=250,
    )

    orchestrator._prepare_conversation = AsyncMock(return_value=context)

    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)

    async def fake_stream(request):
        yield LLMStreamChunk(content="Hello")

    orchestrator._stream_with_retry = fake_stream

    orchestrator.message_service.create_assistant_message = AsyncMock()

    async for _ in orchestrator.stream_message(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    ):
        pass

    orchestrator.rate_limit_service.check_cost_token_limit.assert_called_once()

    call = orchestrator.rate_limit_service.check_cost_token_limit.call_args

    assert call.kwargs["user_id"] == user_id
    assert call.kwargs["input_tokens"] == 250


@pytest.mark.asyncio
async def test_stream_does_not_call_provider_when_limit_fails(
    orchestrator,
):
    from app.exceptions.rate_limit import UserQuotaExceededError

    user_id = uuid4()
    chat_id = uuid4()

    context = make_context(
        estimated_tokens=100,
    )

    orchestrator._prepare_conversation = AsyncMock(return_value=context)

    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)

    orchestrator.rate_limit_service.check_cost_token_limit.side_effect = (
        UserQuotaExceededError()
    )

    orchestrator._stream_with_retry = AsyncMock()

    with pytest.raises(UserQuotaExceededError):
        async for _ in orchestrator.stream_message(
            chat_id=chat_id,
            user_id=user_id,
            content="Hello",
        ):
            pass

    orchestrator._stream_with_retry.assert_not_called()
    orchestrator.rate_limit_service.record_provider_usage.assert_not_called()
