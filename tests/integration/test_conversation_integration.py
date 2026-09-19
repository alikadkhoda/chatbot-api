import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.exceptions.provider import LLMProviderError, LLMProviderTransientError
from app.exceptions.rate_limit import RateLimitExceededError
from app.exceptions.tool import ToolExecutionError
from app.infrastructure.rate_limit.result import (
    RateLimitResult,
    RequestRateLimitResult,
    UsageReservationResult,
)
from app.schemas.llm import (
    LLMMessage,
    LLMMessageRole,
    LLMResponse,
    LLMStreamChunk,
    LLMUsage,
)
from app.schemas.tool import ToolCall, ToolResult
from app.services.conversation import ConversationOrchestratorService
from app.services.rate_limit import RateLimitService, RateLimitStore

COST_SCALE = 1_000_000


class InMemoryRateLimitStore(RateLimitStore):
    """Deterministic store used to exercise the real rate-limit service."""

    def __init__(self):
        self.request_count = 0
        self.reserved = []
        self.settled = []
        self.released = []

    async def get_request_minute_count(self, user_id):
        return self.request_count

    async def increment_request(self, user_id, minute_limit, daily_limit):
        if self.request_count >= minute_limit:
            return RequestRateLimitResult(
                allowed=False,
                minute_current=minute_limit,
                daily_current=self.request_count,
            )

        if self.request_count >= daily_limit:
            return RequestRateLimitResult(
                allowed=False,
                minute_current=self.request_count,
                daily_current=daily_limit,
            )

        self.request_count += 1
        return RequestRateLimitResult(
            allowed=True,
            minute_current=self.request_count,
            daily_current=self.request_count,
        )

    async def get_token_count(self, user_id):
        return None

    async def increment_tokens(self, user_id, tokens, limit):
        return RateLimitResult(allowed=True, current=tokens)

    async def get_cost(self, user_id):
        return None

    async def increment_cost(self, user_id, cost, limit):
        scaled_cost = int(Decimal(str(cost)) * COST_SCALE)

        return RateLimitResult(allowed=True, current=scaled_cost)

    async def reserve_usage(self, user_id, tokens, cost, token_limit, cost_limit):
        self.reserved.append((user_id, tokens, cost))
        return UsageReservationResult(
            allowed=True,
            token_current=tokens,
            cost_current=cost,
        )

    async def settle_usage(self, user_id, tokens, cost, reserved_tokens, reserved_cost):
        self.settled.append((user_id, tokens, cost, reserved_tokens, reserved_cost))

    async def release_usage(self, user_id, reserved_tokens, reserved_cost):
        self.released.append((user_id, reserved_tokens, reserved_cost))

    async def delete_user(self, user_id):
        return None


@pytest.fixture
def integration_setup():
    store = InMemoryRateLimitStore()
    rate_limit = RateLimitService(
        store=store,
        max_requests_per_minute=10,
        max_requests_per_day=100,
        max_tokens_per_request=10_000,
        max_tokens_per_day=100_000,
        max_estimated_cost_per_day=100.0,
        input_cost_per_1k_tokens=1.0,
        output_cost_per_1k_tokens=2.0,
    )

    service = ConversationOrchestratorService.__new__(ConversationOrchestratorService)
    service.provider = Mock()
    service.tool_registry = Mock()
    service.tool_registry.definitions.return_value = []
    service.rate_limit_service = rate_limit
    service.message_service = Mock()
    service.chat_service = Mock()
    service.context_builder = Mock()
    service.summary_service = Mock()
    service._prepare_conversation = AsyncMock(
        return_value=Mock(
            messages=[LLMMessage(role=LLMMessageRole.USER, content="Hello")],
            estimated_tokens=7,
            should_summarize=False,
            omitted_messages=[],
        )
    )
    service._update_summary_if_needed = AsyncMock(
        side_effect=lambda **kwargs: kwargs["context"]
    )
    service.message_service.create_assistant_message = AsyncMock(return_value=Mock())

    return service, store


@pytest.mark.asyncio
async def test_non_streaming_integrates_request_reservation_settlement_and_persistence(
    integration_setup,
):
    service, store = integration_setup
    user_id = uuid4()
    chat_id = uuid4()
    events = []

    async def generate(request):
        events.append("provider")
        return LLMResponse(
            content="Hello back", usage=LLMUsage(input_tokens=10, output_tokens=4)
        )

    service.provider.generate = generate

    original_settle = store.settle_usage

    async def settle(*args, **kwargs):
        events.append("settle")
        await original_settle(*args, **kwargs)

    store.settle_usage = settle

    async def persist(**kwargs):
        events.append("persist")
        return Mock()

    service.message_service.create_assistant_message = persist

    await service.send_message(chat_id=chat_id, user_id=user_id, content="Hello")

    assert events == ["provider", "settle", "persist"]
    assert len(store.reserved) == 1
    assert len(store.settled) == 1
    assert store.released == []


@pytest.mark.asyncio
async def test_non_streaming_transient_retry_keeps_one_reservation_and_one_settlement(
    integration_setup, monkeypatch
):
    service, store = integration_setup
    user_id = uuid4()
    chat_id = uuid4()
    attempts = 0

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    async def generate(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise LLMProviderTransientError()
        return LLMResponse(
            content="Recovered", usage=LLMUsage(input_tokens=11, output_tokens=5)
        )

    service.provider.generate = generate

    await service.send_message(chat_id=chat_id, user_id=user_id, content="Hello")

    assert attempts == 2
    assert len(store.reserved) == 1
    assert len(store.settled) == 1
    assert store.released == []


@pytest.mark.asyncio
async def test_non_streaming_tool_loop_uses_one_reservation_per_provider_call(
    integration_setup,
):
    service, store = integration_setup
    user_id = uuid4()
    chat_id = uuid4()

    tool_call = ToolCall(id="call_1", tool_name="validate", arguments={"value": "ok"})
    tool = Mock()
    tool.execute = AsyncMock(return_value=ToolResult(content="valid"))
    service.tool_registry.get.return_value = tool

    responses = iter(
        [
            LLMResponse(
                content="I will validate it.",
                tool_calls=[tool_call],
                usage=LLMUsage(input_tokens=10, output_tokens=3),
            ),
            LLMResponse(
                content="The value is valid.",
                usage=LLMUsage(input_tokens=18, output_tokens=6),
            ),
        ]
    )

    async def generate(request):
        return next(responses)

    service.provider.generate = generate

    await service.send_message(chat_id=chat_id, user_id=user_id, content="Validate")

    assert len(store.reserved) == 2
    assert len(store.settled) == 2
    assert store.released == []
    tool.execute.assert_awaited_once_with({"value": "ok"})
    service.message_service.create_assistant_message.assert_awaited_once_with(
        chat_id=chat_id, user_id=user_id, content="The value is valid."
    )


@pytest.mark.asyncio
async def test_streaming_integrates_usage_settlement_and_persistence(integration_setup):
    service, store = integration_setup
    user_id = uuid4()
    chat_id = uuid4()
    events = []

    async def generate_stream(request):
        events.append("provider")
        yield LLMStreamChunk(content="Hello ")
        yield LLMStreamChunk(
            content="world", usage=LLMUsage(input_tokens=12, output_tokens=6)
        )

    service.provider.generate_stream = generate_stream

    original_settle = store.settle_usage

    async def settle(*args, **kwargs):
        events.append("settle")
        await original_settle(*args, **kwargs)

    store.settle_usage = settle

    async def persist(**kwargs):
        events.append("persist")
        return Mock()

    service.message_service.create_assistant_message = persist

    chunks = [
        chunk
        async for chunk in service.stream_message(
            chat_id=chat_id, user_id=user_id, content="Hello"
        )
    ]

    assert chunks == ["data: Hello \n\n", "data: world\n\n"]
    assert events == ["provider", "settle", "persist"]
    assert store.settled[0][1:3] == (18, 0.024)
    assert store.released == []


# test_streaming_provider_failure_releases_reservation_without_settlement_or_persistence
@pytest.mark.asyncio
async def test_streaming_provider_failure_releases_reservation(
    integration_setup,
):
    service, store = integration_setup
    user_id = uuid4()
    chat_id = uuid4()

    async def generate_stream(request):
        raise LLMProviderError()
        yield  # pragma: no cover

    service.provider.generate_stream = generate_stream

    chunks = [
        chunk
        async for chunk in service.stream_message(
            chat_id=chat_id,
            user_id=user_id,
            content="Hello",
        )
    ]

    assert any("LLM_PROVIDER_ERROR" in chunk for chunk in chunks)
    assert len(store.reserved) == 1
    assert store.settled == []
    assert len(store.released) == 1
    service.message_service.create_assistant_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_limit_rejection_stops_conversation_before_provider_call(
    integration_setup,
):
    service, store = integration_setup
    user_id = uuid4()
    chat_id = uuid4()

    service.rate_limit_service = RateLimitService(
        store=store,
        max_requests_per_minute=1,
        max_requests_per_day=100,
        max_tokens_per_request=10_000,
        max_tokens_per_day=100_000,
        max_estimated_cost_per_day=100.0,
        input_cost_per_1k_tokens=1.0,
        output_cost_per_1k_tokens=2.0,
    )

    service.provider.generate = AsyncMock(
        return_value=LLMResponse(
            content="first response", usage=LLMUsage(input_tokens=10, output_tokens=4)
        )
    )

    await service.send_message(
        chat_id=chat_id, user_id=user_id, content="First request"
    )

    service.provider.generate.reset_mock()
    service.message_service.create_assistant_message.reset_mock()

    with pytest.raises(RateLimitExceededError):
        await service.send_message(
            chat_id=chat_id, user_id=user_id, content="Second request"
        )

    service.provider.generate.assert_not_awaited()
    service.message_service.create_assistant_message.assert_not_awaited()
    assert len(store.reserved) == 1
    assert len(store.settled) == 1
    assert store.released == []


@pytest.mark.asyncio
async def test_tool_execution_failure_does_not_create_second_reservation_or_persist(
    integration_setup,
):
    service, store = integration_setup
    user_id = uuid4()
    chat_id = uuid4()

    tool_call = ToolCall(
        id="call-1",
        tool_name="validate",
        arguments={"value": "ok"},
    )
    tool = Mock()
    tool.execute = AsyncMock(side_effect=RuntimeError("tool failed"))
    service.tool_registry.get.return_value = tool

    service.provider.generate = AsyncMock(
        return_value=LLMResponse(
            content="I will validate it.",
            tool_calls=[tool_call],
            usage=LLMUsage(input_tokens=10, output_tokens=3),
        )
    )

    with pytest.raises(ToolExecutionError):
        await service.send_message(
            chat_id=chat_id,
            user_id=user_id,
            content="Validate",
        )

    assert len(store.reserved) == 1
    assert len(store.settled) == 1
    assert store.released == []
    service.message_service.create_assistant_message.assert_not_awaited()
    tool.execute.assert_awaited_once_with({"value": "ok"})


@pytest.mark.asyncio
async def test_concurrent_conversations_keep_provider_usage_reservations_independent(
    integration_setup,
):
    service, store = integration_setup
    user_ids = [uuid4(), uuid4()]
    chat_ids = [uuid4(), uuid4()]

    calls = 0

    async def generate(request):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return LLMResponse(
            content=f"response-{calls}",
            usage=LLMUsage(input_tokens=10, output_tokens=4),
        )

    service.provider.generate = generate

    await asyncio.gather(
        service.send_message(
            chat_id=chat_ids[0], user_id=user_ids[0], content="Hello 1"
        ),
        service.send_message(
            chat_id=chat_ids[1], user_id=user_ids[1], content="Hello 2"
        ),
    )

    assert calls == 2
    assert len(store.reserved) == 2
    assert len(store.settled) == 2
    assert store.released == []
    assert {entry[0] for entry in store.reserved} == set(user_ids)
    assert {entry[0] for entry in store.settled} == set(user_ids)
