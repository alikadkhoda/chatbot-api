from app.schemas.llm import LLMMessage, LLMMessageRole
from app.schemas.tool import ToolCall
from app.services.conversation_context import ConversationContextBuilder


def test_build_adds_system_prompt():
    builder = ConversationContextBuilder(
        max_tokens=1000,
        reserve_tokens=200,
        summary_trigger_tokens=700,
    )

    result = builder.build(
        [
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ],
        system_prompt="You are helpful.",
    )

    assert result.messages[0].role is LLMMessageRole.SYSTEM
    assert result.messages[0].content == "You are helpful."


def test_build_adds_summary():
    builder = ConversationContextBuilder(
        max_tokens=1000,
        reserve_tokens=200,
        summary_trigger_tokens=700,
    )

    result = builder.build(
        [
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ],
        system_prompt="You are helpful.",
        summary="The user is building a FastAPI app.",
    )

    assert result.messages[0].role is LLMMessageRole.SYSTEM
    assert result.messages[1].role is LLMMessageRole.SYSTEM

    assert "FastAPI" in result.messages[1].content


def test_tool_call_and_result_are_kept_together():
    builder = ConversationContextBuilder(
        max_tokens=100,
        reserve_tokens=20,
        summary_trigger_tokens=50,
    )

    assistant = LLMMessage(
        role=LLMMessageRole.ASSISTANT,
        content="",
        tool_calls=[
            ToolCall(
                tool_name="validate_bank_card",
                arguments={"card_number": "123"},
            )
        ],
    )

    tool = LLMMessage(
        role=LLMMessageRole.TOOL,
        content="invalid",
        tool_name="validate_bank_card",
    )

    result = builder.build(
        [
            LLMMessage(
                role=LLMMessageRole.USER,
                content="old message " * 10,
            ),
            assistant,
            tool,
        ],
        system_prompt="You are helpful.",
    )

    selected = result.messages

    if assistant in selected:
        assert tool in selected


def test_context_requests_summary_when_old_messages_are_omitted():
    builder = ConversationContextBuilder(
        max_tokens=80,
        reserve_tokens=10,
        summary_trigger_tokens=50,
    )

    messages = [
        LLMMessage(
            role=LLMMessageRole.USER,
            content="old " * 20,
        ),
        LLMMessage(
            role=LLMMessageRole.ASSISTANT,
            content="old answer " * 20,
        ),
        LLMMessage(
            role=LLMMessageRole.USER,
            content="latest",
        ),
    ]

    result = builder.build(
        messages,
        system_prompt="system",
    )

    assert result.omitted_messages
    assert result.should_summarize is True
