from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.exceptions.rate_limit import UserQuotaExceededError
from app.infrastructure.rate_limit.result import UsageReservation
from app.schemas.llm import (
    LLMMessage,
    LLMMessageRole,
    LLMResponse,
    LLMUsage,
)
from app.schemas.tool import ToolCall
from app.services.conversation_summary import ConversationSummaryService


@pytest.fixture
def provider():
    return Mock()


@pytest.fixture
def rate_limit_service():
    service = Mock()

    service.check_cost_token_limit = AsyncMock(
        return_value=UsageReservation(tokens=1000, cost=1.0)
    )
    service.record_provider_usage = AsyncMock()
    service.release_usage = AsyncMock()

    return service


@pytest.fixture
def summary_service(provider, rate_limit_service):
    return ConversationSummaryService(
        provider=provider,
        rate_limit_service=rate_limit_service,
    )


@pytest.mark.asyncio
async def test_empty_messages_return_existing_summary(
    summary_service,
    provider,
):
    result = await summary_service.summarize(
        user_id=uuid4(),
        messages=[],
        existing_summary="Existing summary",
    )

    assert result == "Existing summary"
    provider.generate.assert_not_called()


@pytest.mark.asyncio
async def test_summary_calls_provider(summary_service, provider):
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content="The user is building a FastAPI application.",
            usage=LLMUsage(
                input_tokens=100,
                output_tokens=20,
            ),
        )
    )

    user_id = uuid4()

    result = await summary_service.summarize(
        user_id=user_id,
        messages=[
            LLMMessage(
                role=LLMMessageRole.USER,
                content="I am building a FastAPI application.",
            )
        ],
    )

    assert result == "The user is building a FastAPI application."

    provider.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_summary_records_actual_provider_usage(
    summary_service,
    provider,
    rate_limit_service,
):
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content="Summary",
            usage=LLMUsage(
                input_tokens=123,
                output_tokens=45,
            ),
        )
    )

    user_id = uuid4()

    await summary_service.summarize(
        user_id=user_id,
        messages=[
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ],
    )

    reservation = rate_limit_service.check_cost_token_limit.return_value

    rate_limit_service.record_provider_usage.assert_awaited_once_with(
        user_id=user_id,
        input_tokens=123,
        output_tokens=45,
        reservation=reservation,
    )
    rate_limit_service.release_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_summary_releases_reservation_when_provider_fails(
    summary_service,
    provider,
    rate_limit_service,
):
    provider.generate = AsyncMock(side_effect=RuntimeError("provider failed"))

    user_id = uuid4()

    result = await summary_service.summarize(
        user_id=user_id,
        messages=[
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ],
        existing_summary="Old summary",
    )

    assert result == "Old summary"
    rate_limit_service.release_usage.assert_awaited_once_with(
        user_id=user_id,
        reservation=rate_limit_service.check_cost_token_limit.return_value,
    )
    rate_limit_service.record_provider_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_summary_uses_estimated_output_when_provider_usage_missing(
    summary_service,
    provider,
    rate_limit_service,
):
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content="This is the generated summary.",
            usage=None,
        )
    )

    user_id = uuid4()

    await summary_service.summarize(
        user_id=user_id,
        messages=[
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ],
    )

    call = rate_limit_service.record_provider_usage.call_args
    reservation = rate_limit_service.check_cost_token_limit.return_value

    assert call.kwargs["user_id"] == user_id
    assert call.kwargs["reservation"] is reservation
    assert call.kwargs["input_tokens"] > 0
    assert call.kwargs["output_tokens"] > 0


@pytest.mark.asyncio
async def test_summary_checks_cost_token_limit_before_provider_call(
    summary_service,
    provider,
    rate_limit_service,
):
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content="Summary",
            usage=LLMUsage(
                input_tokens=100,
                output_tokens=20,
            ),
        )
    )

    user_id = uuid4()

    await summary_service.summarize(
        user_id=user_id,
        messages=[
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ],
    )

    rate_limit_service.check_cost_token_limit.assert_called_once()

    check_call = rate_limit_service.check_cost_token_limit.call_args

    assert check_call.kwargs["user_id"] == user_id
    assert check_call.kwargs["input_tokens"] > 0
    assert check_call.kwargs["max_output_tokens"] > 0


@pytest.mark.asyncio
async def test_summary_does_not_record_usage_when_provider_fails(
    summary_service,
    provider,
    rate_limit_service,
):
    provider.generate = AsyncMock(side_effect=RuntimeError("provider failed"))

    user_id = uuid4()

    result = await summary_service.summarize(
        user_id=user_id,
        messages=[
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ],
        existing_summary="Old summary",
    )

    assert result == "Old summary"

    rate_limit_service.record_provider_usage.assert_not_awaited()
    rate_limit_service.release_usage.assert_awaited_once_with(
        user_id=user_id,
        reservation=rate_limit_service.check_cost_token_limit.return_value,
    )


@pytest.mark.asyncio
async def test_summary_quota_error_is_propagated(
    summary_service,
    provider,
    rate_limit_service,
):
    rate_limit_service.check_cost_token_limit.side_effect = UserQuotaExceededError()

    user_id = uuid4()

    with pytest.raises(UserQuotaExceededError):
        await summary_service.summarize(
            user_id=user_id,
            messages=[
                LLMMessage(
                    role=LLMMessageRole.USER,
                    content="Hello",
                )
            ],
        )

    provider.generate.assert_not_called()
    rate_limit_service.record_provider_usage.assert_not_awaited()
    rate_limit_service.release_usage.assert_not_awaited()


def test_format_tool_message(summary_service):
    message = LLMMessage(
        role=LLMMessageRole.TOOL,
        content="valid",
        tool_name="validate_bank_card",
    )

    result = summary_service._format_message(message)

    assert result == "tool (validate_bank_card): valid"


def test_format_assistant_tool_call(summary_service):
    message = LLMMessage(
        role=LLMMessageRole.ASSISTANT,
        content="",
        tool_calls=[
            ToolCall(
                tool_name="validate_bank_card",
                arguments={"card_number": "123"},
            )
        ],
    )

    result = summary_service._format_message(message)

    assert "assistant used tools: validate_bank_card" in result
