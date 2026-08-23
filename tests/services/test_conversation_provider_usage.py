from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.exceptions.tool import ToolLoopLimitError
from app.schemas.llm import (
    LLMMessage,
    LLMMessageRole,
    LLMResponse,
    LLMUsage,
)
from app.schemas.tool import ToolCall
from app.services.conversation import ConversationOrchestratorService


@pytest.fixture
def orchestrator():
    service = ConversationOrchestratorService.__new__(ConversationOrchestratorService)

    service.provider = Mock()
    service.tool_registry = Mock()
    service.rate_limit_service = Mock()

    return service


def make_context(messages, estimated_tokens):
    context = Mock()
    context.messages = messages
    context.estimated_tokens = estimated_tokens
    return context


@pytest.mark.asyncio
async def test_generate_with_tools_records_actual_provider_usage(
    orchestrator,
):
    user_id = uuid4()

    response = LLMResponse(
        content="Hello",
        usage=LLMUsage(
            input_tokens=120,
            output_tokens=30,
        ),
    )

    orchestrator._generate_with_retry = AsyncMock(return_value=response)

    orchestrator.tool_registry.definitions.return_value = []

    context = make_context(
        [
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ],
        estimated_tokens=100,
    )

    result = await orchestrator._generate_with_tools(
        user_id=user_id,
        context=context,
    )

    assert result is response

    orchestrator.rate_limit_service.record_provider_usage.assert_called_once_with(
        user_id=user_id,
        input_tokens=120,
        output_tokens=30,
    )


@pytest.mark.asyncio
async def test_generate_with_tools_uses_fallback_usage_when_provider_has_none(
    orchestrator,
):
    user_id = uuid4()

    response = LLMResponse(
        content="Hello world",
        usage=None,
    )

    orchestrator._generate_with_retry = AsyncMock(return_value=response)

    orchestrator.tool_registry.definitions.return_value = []

    context = make_context(
        [
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ],
        estimated_tokens=100,
    )

    await orchestrator._generate_with_tools(
        user_id=user_id,
        context=context,
    )

    call = orchestrator.rate_limit_service.record_provider_usage.call_args

    expected_tokens = 7  # مقدار واقعی محاسبه‌شده توسط estimate_message_tokens
    assert call.kwargs["user_id"] == user_id
    assert call.kwargs["input_tokens"] == expected_tokens
    assert call.kwargs["output_tokens"] > 0


@pytest.mark.asyncio
async def test_generate_checks_limit_before_provider_call(
    orchestrator,
):
    user_id = uuid4()

    response = LLMResponse(
        content="Hello",
        usage=LLMUsage(
            input_tokens=100,
            output_tokens=20,
        ),
    )

    orchestrator._generate_with_retry = AsyncMock(return_value=response)

    orchestrator.tool_registry.definitions.return_value = []

    context = make_context(
        [
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ],
        estimated_tokens=100,
    )

    await orchestrator._generate_with_tools(
        user_id=user_id,
        context=context,
    )

    orchestrator.rate_limit_service.check_cost_token_limit.assert_called_once()

    check_call = orchestrator.rate_limit_service.check_cost_token_limit.call_args

    expected_tokens = 7  # مقدار واقعی محاسبه‌شده توسط estimate_message_tokens
    assert check_call.kwargs["user_id"] == user_id
    assert check_call.kwargs["input_tokens"] == expected_tokens


#####################################################


@pytest.mark.asyncio
async def test_generate_does_not_record_usage_when_provider_fails(
    orchestrator,
):
    user_id = uuid4()

    orchestrator._generate_with_retry = AsyncMock(
        side_effect=RuntimeError("provider failure")
    )

    orchestrator.tool_registry.definitions.return_value = []

    context = make_context(
        [
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ],
        estimated_tokens=100,
    )

    with pytest.raises(RuntimeError):
        await orchestrator._generate_with_tools(
            user_id=user_id,
            context=context,
        )

    orchestrator.rate_limit_service.record_provider_usage.assert_not_called()


@pytest.mark.asyncio
async def test_each_provider_call_records_its_own_usage(
    orchestrator,
):
    user_id = uuid4()

    tool_call = ToolCall(
        tool_name="validate_bank_card",
        arguments={"card_number": "123"},
    )
    tool_call.tool_name = "validate_bank_card"
    tool_call.arguments = {"card_number": "123"}

    first_response = LLMResponse(
        content="validate card.",
        tool_calls=[tool_call],
        usage=LLMUsage(
            input_tokens=100,
            output_tokens=10,
        ),
    )

    second_response = LLMResponse(
        content="The card is valid.",
        tool_calls=[],
        usage=LLMUsage(
            input_tokens=150,
            output_tokens=20,
        ),
    )

    orchestrator._generate_with_retry = AsyncMock(
        side_effect=[
            first_response,
            second_response,
        ]
    )

    orchestrator.tool_registry.definitions.return_value = []

    orchestrator._execute_tool_call = AsyncMock(return_value="valid")

    context = make_context(
        [
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Validate my card",
            )
        ],
        estimated_tokens=100,
    )

    result = await orchestrator._generate_with_tools(
        user_id=user_id,
        context=context,
    )

    assert result is second_response

    assert orchestrator.rate_limit_service.record_provider_usage.call_count == 2

    calls = orchestrator.rate_limit_service.record_provider_usage.call_args_list

    assert calls[0].kwargs == {
        "user_id": user_id,
        "input_tokens": 100,
        "output_tokens": 10,
    }

    assert calls[1].kwargs == {
        "user_id": user_id,
        "input_tokens": 150,
        "output_tokens": 20,
    }


########
@pytest.mark.asyncio
async def test_cost_token_limit_is_checked_before_each_provider_call(
    orchestrator,
):
    user_id = uuid4()

    tool_call = ToolCall(
        tool_name="validate_bank_card",
        arguments={"card_number": "123"},
    )

    first_response = LLMResponse(
        content="validate card",
        tool_calls=[tool_call],
        usage=LLMUsage(
            input_tokens=100,
            output_tokens=10,
        ),
    )

    second_response = LLMResponse(
        content="Done",
        usage=LLMUsage(
            input_tokens=150,
            output_tokens=20,
        ),
    )

    orchestrator._generate_with_retry = AsyncMock(
        side_effect=[
            first_response,
            second_response,
        ]
    )

    orchestrator.tool_registry.definitions.return_value = []

    orchestrator._execute_tool_call = AsyncMock(
        return_value="valid",
    )

    context = make_context(
        [
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Validate",
            )
        ],
        estimated_tokens=100,
    )

    await orchestrator._generate_with_tools(
        user_id=user_id,
        context=context,
    )

    assert orchestrator.rate_limit_service.check_cost_token_limit.call_count == 2


##################
@pytest.mark.asyncio
async def test_second_provider_call_uses_updated_conversation_tokens(
    orchestrator,
):
    user_id = uuid4()

    tool_call = ToolCall(
        tool_name="validate_bank_card",
        arguments={"card_number": "123"},
    )

    first_response = LLMResponse(
        content="validate card",
        tool_calls=[tool_call],
        usage=LLMUsage(
            input_tokens=100,  # ← مصرف واقعی (برای record_provider_usage)
            output_tokens=10,
        ),
    )

    second_response = LLMResponse(
        content="Done",
        usage=LLMUsage(
            input_tokens=180,  # ← مصرف واقعی (برای record_provider_usage)
            output_tokens=20,
        ),
    )

    orchestrator._generate_with_retry = AsyncMock(
        side_effect=[
            first_response,
            second_response,
        ]
    )

    orchestrator.tool_registry.definitions.return_value = []

    orchestrator._execute_tool_call = AsyncMock(
        return_value="valid",
    )

    context = make_context(
        [
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Validate",
            )
        ],
        estimated_tokens=100,
    )

    await orchestrator._generate_with_tools(
        user_id=user_id,
        context=context,
    )

    # ============================================================
    # بررسی check_cost_token_limit (تخمین محلی)
    # ============================================================
    check_calls = orchestrator.rate_limit_service.check_cost_token_limit.call_args_list

    # ✅ بار اول: تخمین برای USER + "Validate" = 7
    first_check = check_calls[0].kwargs["input_tokens"]
    assert first_check == 7

    # ✅ بار دوم: تخمین برای USER + ASSISTANT + TOOL = 41
    second_check = check_calls[1].kwargs["input_tokens"]
    assert second_check == 41

    # تأیید اینکه تخمین دوم بزرگتر است
    assert second_check > first_check

    # ============================================================
    # بررسی record_provider_usage (مصرف واقعی از Provider)
    # ============================================================
    record_calls = orchestrator.rate_limit_service.record_provider_usage.call_args_list

    # ✅ بار اول: مصرف واقعی = 100
    first_record = record_calls[0].kwargs
    assert first_record["input_tokens"] == 100
    assert first_record["output_tokens"] == 10

    # ✅ بار دوم: مصرف واقعی = 180
    second_record = record_calls[1].kwargs
    assert second_record["input_tokens"] == 180
    assert second_record["output_tokens"] == 20


######


@pytest.mark.asyncio
async def test_tool_loop_limit_does_not_allow_unbounded_provider_calls(
    orchestrator,
):
    user_id = uuid4()

    tool_call = ToolCall(
        tool_name="validate_bank_card",
        arguments={"card_number": "123"},
    )

    response = LLMResponse(
        content="validate card",
        tool_calls=[tool_call],
        usage=LLMUsage(
            input_tokens=100,
            output_tokens=10,
        ),
    )

    orchestrator._generate_with_retry = AsyncMock(return_value=response)

    orchestrator.tool_registry.definitions.return_value = []

    orchestrator._execute_tool_call = AsyncMock(
        return_value="valid",
    )

    context = make_context(
        [
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Validate",
            )
        ],
        estimated_tokens=100,
    )

    with pytest.raises(ToolLoopLimitError):
        await orchestrator._generate_with_tools(
            user_id=user_id,
            context=context,
        )

    assert (
        orchestrator._generate_with_retry.await_count
        == orchestrator.MAX_TOOL_ITERATIONS
    )
