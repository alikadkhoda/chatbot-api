from collections.abc import AsyncIterator
from uuid import UUID

from app.exceptions.provider import LLMProviderError
from app.exceptions.tool import (
    ToolExecutionError,
    ToolLoopLimitError,
    ToolNotFoundError,
)
from app.providers.llm import LLMProvider
from app.schemas.llm import LLMMessage, LLMMessageRole, LLMRequest, LLMResponse
from app.schemas.message import MessageCreate, MessageRead
from app.schemas.tool import ToolCall
from app.services.chat import ChatService
from app.services.message import MessageService
from app.tools.registry import ToolRegistry


class ConversationOrchestratorService:
    MAX_TOOL_ITERATIONS = 3

    def __init__(
        self,
        chat_service: ChatService,
        message_service: MessageService,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
    ) -> None:
        self.chat_service = chat_service
        self.message_service = message_service
        self.provider = provider
        self.tool_registry = tool_registry

    async def _prepare_conversation(
        self,
        chat_id: UUID,
        user_id: UUID,
        content: str,
    ) -> list[LLMMessage]:
        await self.chat_service.get_chat(
            chat_id=chat_id,
            user_id=user_id,
        )

        await self.message_service.create_user_message(
            chat_id=chat_id,
            user_id=user_id,
            data=MessageCreate(content=content),
        )

        return await self.message_service.get_llm_messages(
            chat_id=chat_id,
            user_id=user_id,
        )

    async def _execute_tool_call(self, tool_call: ToolCall) -> str:
        tool = self.tool_registry.get(tool_call.tool_name)
        if tool is None:
            raise ToolNotFoundError()

        try:
            result = await tool.execute(tool_call.arguments)
        except Exception as ex:
            raise ToolExecutionError() from ex

        return result.content

    async def _generate_with_tools(self, messages: list[LLMMessage]) -> LLMResponse:
        conversation = list(messages)
        tools = self.tool_registry.definitions()

        for _ in range(self.MAX_TOOL_ITERATIONS):
            response = await self.provider.generate(
                LLMRequest(messages=conversation, tools=tools)
            )
            print(response)

            if not response.tool_calls:
                return response

            conversation.append(
                LLMMessage(
                    role=LLMMessageRole.ASSISTANT,
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                )
            )

            for tool_call in response.tool_calls:
                result = await self._execute_tool_call(tool_call=tool_call)
                conversation.append(
                    LLMMessage(
                        role=LLMMessageRole.TOOL,
                        content=result,
                        tool_name=tool_call.tool_name,
                        tool_call_id=tool_call.id,
                    )
                )

        raise ToolLoopLimitError()

    async def send_message(
        self, chat_id: UUID, user_id: UUID, content: str
    ) -> MessageRead:
        messages = await self._prepare_conversation(
            chat_id=chat_id, user_id=user_id, content=content
        )

        response = await self._generate_with_tools(messages)

        if not response.content:
            raise LLMProviderError()

        assistant = await self.message_service.create_assistant_message(
            chat_id=chat_id, user_id=user_id, content=response.content
        )

        return assistant

    async def stream_message(
        self, chat_id: UUID, user_id: UUID, content: str
    ) -> AsyncIterator[str]:
        messages = await self._prepare_conversation(
            chat_id=chat_id, user_id=user_id, content=content
        )

        buffer: list[str] = []

        async for token in self.provider.generate_stream(LLMRequest(messages=messages)):
            buffer.append(token)

            yield f"data: {token}\n\n"

        await self.message_service.create_assistant_message(
            chat_id=chat_id, user_id=user_id, content="".join(buffer)
        )
