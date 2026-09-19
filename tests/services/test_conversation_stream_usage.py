import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.config import settings
from app.exceptions.provider import LLMProviderError, LLMProviderTransientError
from app.infrastructure.rate_limit.result import UsageReservation
from app.schemas.llm import LLMMessage, LLMMessageRole, LLMStreamChunk, LLMUsage
from app.services.conversation import ConversationOrchestratorService


@pytest.fixture
def orchestrator():
    service = ConversationOrchestratorService.__new__(ConversationOrchestratorService)

    service.provider = Mock()
    service.tool_registry = Mock()

    service.rate_limit_service = Mock()
    service.rate_limit_service.consume_request = AsyncMock()
    service.rate_limit_service.check_cost_token_limit = AsyncMock()
    service.rate_limit_service.record_provider_usage = AsyncMock()
    service.rate_limit_service.release_usage = AsyncMock()

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

    reservation = UsageReservation(
        tokens=145,
        cost=1.0,
    )

    orchestrator.rate_limit_service.check_cost_token_limit = AsyncMock(
        return_value=reservation
    )

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

    orchestrator.rate_limit_service.record_provider_usage.assert_awaited_once_with(
        user_id=user_id,
        input_tokens=120,
        output_tokens=25,
        reservation=reservation,
    )

    orchestrator.rate_limit_service.release_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_uses_last_usage_chunk(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    reservation = UsageReservation(
        tokens=245,
        cost=1.5,
    )

    orchestrator.rate_limit_service.check_cost_token_limit = AsyncMock(
        return_value=reservation
    )

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

    orchestrator.rate_limit_service.record_provider_usage.assert_awaited_once_with(
        user_id=user_id,
        input_tokens=210,
        output_tokens=45,
        reservation=reservation,
    )

    orchestrator.rate_limit_service.release_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_falls_back_to_estimated_usage(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    reservation = UsageReservation(
        tokens=100,
        cost=1.0,
    )

    orchestrator.rate_limit_service.check_cost_token_limit = AsyncMock(
        return_value=reservation
    )

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

    orchestrator.rate_limit_service.record_provider_usage.assert_awaited_once()

    call = orchestrator.rate_limit_service.record_provider_usage.await_args

    assert call.kwargs["user_id"] == user_id
    assert call.kwargs["input_tokens"] == 100
    assert call.kwargs["output_tokens"] > 0
    assert call.kwargs["reservation"] == reservation

    orchestrator.rate_limit_service.release_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_failure_releases_reservation_without_recording_usage(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    reservation = UsageReservation(
        tokens=100,
        cost=1.0,
    )

    orchestrator.rate_limit_service.check_cost_token_limit = AsyncMock(
        return_value=reservation
    )

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

    orchestrator.rate_limit_service.record_provider_usage.assert_not_awaited()

    orchestrator.rate_limit_service.release_usage.assert_awaited_once_with(
        user_id=user_id,
        reservation=reservation,
    )

    orchestrator.message_service.create_assistant_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_cancellation_releases_reservation_without_recording_usage(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    reservation = UsageReservation(
        tokens=100,
        cost=1.0,
    )

    orchestrator.rate_limit_service.check_cost_token_limit = AsyncMock(
        return_value=reservation
    )

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

    orchestrator.rate_limit_service.record_provider_usage.assert_not_awaited()

    orchestrator.rate_limit_service.release_usage.assert_awaited_once_with(
        user_id=user_id,
        reservation=reservation,
    )


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

    orchestrator._stream_with_retry.assert_not_awaited()

    orchestrator.rate_limit_service.record_provider_usage.assert_not_awaited()

    orchestrator.rate_limit_service.release_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_empty_response_releases_reservation(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    reservation = UsageReservation(
        tokens=100,
        cost=1.0,
    )

    orchestrator.rate_limit_service.check_cost_token_limit = AsyncMock(
        return_value=reservation
    )

    context = make_context(
        estimated_tokens=100,
    )

    orchestrator._prepare_conversation = AsyncMock(return_value=context)

    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)

    orchestrator.tool_registry.definitions.return_value = []

    async def fake_stream(request):
        yield LLMStreamChunk(content=None)
        yield LLMStreamChunk(content=None)

    orchestrator._stream_with_retry = fake_stream

    orchestrator.message_service.create_assistant_message = AsyncMock()

    chunks = []

    async for chunk in orchestrator.stream_message(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    ):
        chunks.append(chunk)

    orchestrator.rate_limit_service.release_usage.assert_awaited_once_with(
        user_id=user_id,
        reservation=reservation,
    )

    orchestrator.rate_limit_service.record_provider_usage.assert_not_awaited()

    orchestrator.message_service.create_assistant_message.assert_not_awaited()

    assert any("AI_EMPTY_RESPONSE" in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_stream_unexpected_error_releases_reservation(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    reservation = UsageReservation(
        tokens=100,
        cost=1.0,
    )

    orchestrator.rate_limit_service.check_cost_token_limit = AsyncMock(
        return_value=reservation
    )

    context = make_context(
        estimated_tokens=100,
    )

    orchestrator._prepare_conversation = AsyncMock(return_value=context)

    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)

    orchestrator.tool_registry.definitions.return_value = []

    async def fake_stream(request):
        yield LLMStreamChunk(content="partial")

        raise RuntimeError("unexpected failure")

    orchestrator._stream_with_retry = fake_stream

    orchestrator.message_service.create_assistant_message = AsyncMock()

    chunks = []

    async for chunk in orchestrator.stream_message(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    ):
        chunks.append(chunk)

    orchestrator.rate_limit_service.release_usage.assert_awaited_once_with(
        user_id=user_id,
        reservation=reservation,
    )

    orchestrator.rate_limit_service.record_provider_usage.assert_not_awaited()

    orchestrator.message_service.create_assistant_message.assert_not_awaited()

    assert any("AI_STREAM_ERROR" in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_stream_retries_transient_provider_failure_before_first_chunk(
    orchestrator,
):
    request = Mock()
    attempts = 0

    async def fake_generate_stream(_request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise LLMProviderTransientError()

        yield LLMStreamChunk(content="ok")

    orchestrator.provider.generate_stream = fake_generate_stream
    orchestrator.MAX_PROVIDER_RETRIES = 1

    chunks = []
    async for chunk in orchestrator._stream_with_retry(request=request):
        chunks.append(chunk)

    assert attempts == 2
    assert chunks[0].content == "ok"


@pytest.mark.asyncio
async def test_stream_does_not_retry_after_first_chunk(
    orchestrator,
):
    request = Mock()
    attempts = 0

    async def fake_generate_stream(_request):
        nonlocal attempts
        attempts += 1
        yield LLMStreamChunk(content="partial")
        raise LLMProviderTransientError()

    orchestrator.provider.generate_stream = fake_generate_stream
    orchestrator.MAX_PROVIDER_RETRIES = 2

    with pytest.raises(LLMProviderTransientError):
        async for _ in orchestrator._stream_with_retry(request=request):
            pass

    assert attempts == 1


@pytest.mark.asyncio
async def test_stream_settles_usage_before_persisting_assistant_message(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()
    reservation = UsageReservation(tokens=100, cost=1.0)

    events = []
    orchestrator.rate_limit_service.check_cost_token_limit = AsyncMock(
        return_value=reservation
    )
    orchestrator.rate_limit_service.record_provider_usage = AsyncMock(
        side_effect=lambda **_: events.append("settle")
    )
    orchestrator.message_service.create_assistant_message = AsyncMock(
        side_effect=lambda **_: events.append("persist")
    )

    context = make_context(estimated_tokens=100)
    orchestrator._prepare_conversation = AsyncMock(return_value=context)
    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)
    orchestrator.tool_registry.definitions.return_value = []

    async def fake_stream(request):
        yield LLMStreamChunk(content="Hello")
        yield LLMStreamChunk(usage=LLMUsage(input_tokens=110, output_tokens=5))

    orchestrator._stream_with_retry = fake_stream

    async for _ in orchestrator.stream_message(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    ):
        pass

    assert events == ["settle", "persist"]
    orchestrator.message_service.create_assistant_message.assert_awaited_once_with(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    )


@pytest.mark.asyncio
async def test_stream_does_not_persist_assistant_when_settlement_fails(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()
    reservation = UsageReservation(tokens=100, cost=1.0)

    settlement_error = RuntimeError("settlement failed")
    orchestrator.rate_limit_service.check_cost_token_limit = AsyncMock(
        return_value=reservation
    )
    orchestrator.rate_limit_service.record_provider_usage = AsyncMock(
        side_effect=settlement_error
    )
    orchestrator.message_service.create_assistant_message = AsyncMock()

    context = make_context(estimated_tokens=100)
    orchestrator._prepare_conversation = AsyncMock(return_value=context)
    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)
    orchestrator.tool_registry.definitions.return_value = []

    async def fake_stream(request):
        yield LLMStreamChunk(content="Hello")
        yield LLMStreamChunk(usage=LLMUsage(input_tokens=110, output_tokens=5))

    orchestrator._stream_with_retry = fake_stream

    with pytest.raises(RuntimeError, match="settlement failed"):
        async for _ in orchestrator.stream_message(
            chat_id=chat_id,
            user_id=user_id,
            content="Hello",
        ):
            pass

    orchestrator.message_service.create_assistant_message.assert_not_awaited()
    orchestrator.rate_limit_service.release_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_consumes_request_limit_before_reservation_and_provider(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()
    reservation = UsageReservation(tokens=200, cost=1.0)
    events = []

    orchestrator.rate_limit_service.consume_request = AsyncMock(
        side_effect=lambda **_: events.append("request")
    )
    orchestrator.rate_limit_service.check_cost_token_limit = AsyncMock(
        side_effect=lambda **_: events.append("reserve") or reservation
    )

    context = make_context(estimated_tokens=120)
    orchestrator._prepare_conversation = AsyncMock(return_value=context)
    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)
    orchestrator.tool_registry.definitions.return_value = []
    orchestrator.message_service.create_assistant_message = AsyncMock()

    async def fake_stream(request):
        events.append("provider")
        assert request.messages == context.messages
        assert request.tools == []
        yield LLMStreamChunk(content="ok")

    orchestrator._stream_with_retry = fake_stream

    async for _ in orchestrator.stream_message(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    ):
        pass

    assert events == ["request", "reserve", "provider"]
    orchestrator.rate_limit_service.check_cost_token_limit.assert_awaited_once_with(
        user_id=user_id,
        input_tokens=120,
        max_output_tokens=settings.ai.max_output_tokens,
    )


@pytest.mark.asyncio
async def test_stream_persists_complete_buffer_after_successful_settlement(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()
    reservation = UsageReservation(tokens=100, cost=1.0)

    orchestrator.rate_limit_service.check_cost_token_limit = AsyncMock(
        return_value=reservation
    )
    orchestrator.message_service.create_assistant_message = AsyncMock()

    context = make_context(estimated_tokens=100)
    orchestrator._prepare_conversation = AsyncMock(return_value=context)
    orchestrator._update_summary_if_needed = AsyncMock(return_value=context)
    orchestrator.tool_registry.definitions.return_value = []

    async def fake_stream(request):
        yield LLMStreamChunk(content="Hello ")
        yield LLMStreamChunk(content="world")

    orchestrator._stream_with_retry = fake_stream

    async for _ in orchestrator.stream_message(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    ):
        pass

    orchestrator.message_service.create_assistant_message.assert_awaited_once_with(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello world",
    )


@pytest.mark.asyncio
async def test_stream_releases_reservation_when_transient_retry_is_exhausted(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()
    reservation = UsageReservation(tokens=100, cost=1.0)

    orchestrator.rate_limit_service.check_cost_token_limit = AsyncMock(
        return_value=reservation
    )
    orchestrator._prepare_conversation = AsyncMock(return_value=make_context())
    orchestrator._update_summary_if_needed = AsyncMock(return_value=make_context())
    orchestrator.tool_registry.definitions.return_value = []
    orchestrator.MAX_PROVIDER_RETRIES = 1

    async def fake_stream(request):
        raise LLMProviderTransientError()
        yield  # pragma: no cover

    orchestrator._stream_with_retry = fake_stream

    chunks = []
    async for chunk in orchestrator.stream_message(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    ):
        chunks.append(chunk)

    orchestrator.rate_limit_service.release_usage.assert_awaited_once_with(
        user_id=user_id,
        reservation=reservation,
    )
    orchestrator.rate_limit_service.record_provider_usage.assert_not_awaited()
    assert any("event: error" in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_stream_non_transient_provider_error_is_not_retried(
    orchestrator,
):
    request = Mock()
    attempts = 0

    async def fake_generate_stream(_request):
        nonlocal attempts
        attempts += 1
        raise LLMProviderError()
        yield  # pragma: no cover

    orchestrator.provider.generate_stream = fake_generate_stream

    with pytest.raises(LLMProviderError):
        async for _ in orchestrator._stream_with_retry(request=request):
            pass

    assert attempts == 1
