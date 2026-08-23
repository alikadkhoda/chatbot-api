from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.providers.ollama import OllamaProvider
from app.schemas.llm import (
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)
from app.services.conversation import ConversationOrchestratorService
from app.services.conversation_summary import ConversationSummaryService


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


@pytest.fixture
def provider():
    return Mock()


@pytest.fixture
def rate_limit_service():
    service = Mock()

    service.check_cost_token_limit = Mock()
    service.record_provider_usage = Mock()

    return service


@pytest.fixture
def summary_service(provider, rate_limit_service):
    return ConversationSummaryService(
        provider=provider,
        rate_limit_service=rate_limit_service,
    )


class FakeChunk:
    def __init__(
        self,
        content=None,
        prompt_eval_count=None,
        eval_count=None,
    ):
        self.message = Mock()
        self.message.content = content

        self.prompt_eval_count = prompt_eval_count
        self.eval_count = eval_count


@pytest.mark.asyncio
async def test_ollama_stream_returns_usage_from_final_chunk():
    provider = OllamaProvider(
        host="http://localhost:11434",
        default_model="llama3",
        timeout=30,
    )

    chunks = [
        FakeChunk(content="Hello "),
        FakeChunk(content="world"),
        FakeChunk(
            content="",
            prompt_eval_count=150,
            eval_count=30,
        ),
    ]

    async def fake_ollama_stream():
        for chunk in chunks:
            yield chunk

    provider._client.chat = AsyncMock(return_value=fake_ollama_stream())

    request = LLMRequest(
        messages=[
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ]
    )

    result = []

    async for chunk in provider.generate_stream(request):
        result.append(chunk)

    assert result[0].content == "Hello "
    assert result[1].content == "world"

    assert result[-1].content is None

    assert result[-1].usage is not None
    assert result[-1].usage.input_tokens == 150
    assert result[-1].usage.output_tokens == 30


@pytest.mark.asyncio
async def test_ollama_stream_emits_usage_only_chunk():
    provider = OllamaProvider(
        host="http://localhost:11434",
        default_model="llama3",
        timeout=30,
    )

    final_chunk = FakeChunk(
        content=None,
        prompt_eval_count=321,
        eval_count=54,
    )

    async def fake_ollama_stream():
        yield final_chunk

    provider._client.chat = AsyncMock(return_value=fake_ollama_stream())

    request = LLMRequest(
        messages=[
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Hello",
            )
        ]
    )

    result = []

    async for chunk in provider.generate_stream(request):
        result.append(chunk)

    assert len(result) == 1

    assert result[0].content is None
    assert result[0].usage.input_tokens == 321
    assert result[0].usage.output_tokens == 54


@pytest.mark.asyncio
async def test_summary_includes_existing_summary(
    summary_service,
    provider,
):
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content="Updated summary",
            usage=LLMUsage(
                input_tokens=100,
                output_tokens=20,
            ),
        )
    )

    await summary_service.summarize(
        user_id=uuid4(),
        existing_summary="User prefers concise answers.",
        messages=[
            LLMMessage(
                role=LLMMessageRole.USER,
                content="Continue the project.",
            )
        ],
    )

    request = provider.generate.call_args.kwargs["request"]

    user_prompt = request.messages[1].content

    assert "Existing summary:" in user_prompt
    assert "User prefers concise answers." in user_prompt
    assert "Continue the project." in user_prompt


#################
@pytest.mark.asyncio
async def test_send_message_does_not_record_provider_usage_again(
    orchestrator,
):
    user_id = uuid4()
    chat_id = uuid4()

    response = LLMResponse(
        content="Hello",
        usage=LLMUsage(
            input_tokens=100,
            output_tokens=20,
        ),
    )

    orchestrator.consume_request = Mock()

    orchestrator._prepare_conversation = AsyncMock()
    orchestrator._update_summary_if_needed = AsyncMock()

    orchestrator._generate_with_tools = AsyncMock(return_value=response)

    orchestrator.message_service.create_assistant_message = AsyncMock(
        return_value=Mock()
    )

    await orchestrator.send_message(
        chat_id=chat_id,
        user_id=user_id,
        content="Hello",
    )

    orchestrator.rate_limit_service.record_provider_usage.assert_not_called()
