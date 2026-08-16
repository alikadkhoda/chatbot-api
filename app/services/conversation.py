import asyncio
import json
import logging
from collections.abc import AsyncIterator
from uuid import UUID

from app.exceptions.provider import LLMProviderError, LLMProviderTransientError
from app.exceptions.tool import (
    ToolExecutionError,
    ToolLoopLimitError,
    ToolNotFoundError,
)
from app.providers.llm import LLMProvider
from app.schemas.llm import (
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMResponse,
)
from app.schemas.message import MessageCreate, MessageRead
from app.schemas.tool import ToolCall
from app.services.chat import ChatService
from app.services.conversation_context import (
    ContextBuildResult,
    ConversationContextBuilder,
)
from app.services.conversation_summary import (
    ConversationSummaryService,
)
from app.services.message import MessageService
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ConversationOrchestratorService:
    MAX_TOOL_ITERATIONS = 3
    MAX_PROVIDER_RETRIES = 2

    def __init__(
        self,
        chat_service: ChatService,
        message_service: MessageService,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
        context_builder: ConversationContextBuilder,
        summary_service: ConversationSummaryService,
        system_prompt: str,
    ) -> None:
        self.chat_service = chat_service
        self.message_service = message_service
        self.provider = provider
        self.tool_registry = tool_registry
        self.context_builder = context_builder
        self.summary_service = summary_service
        self.system_prompt = system_prompt

    async def _prepare_conversation(
        self,
        chat_id: UUID,
        user_id: UUID,
        content: str,
    ) -> ContextBuildResult:
        await self.chat_service.get_chat(
            chat_id=chat_id,
            user_id=user_id,
        )

        await self.message_service.create_user_message(
            chat_id=chat_id,
            user_id=user_id,
            data=MessageCreate(content=content),
        )

        messages = await self.message_service.get_llm_messages(
            chat_id=chat_id,
            user_id=user_id,
        )

        summary = await self.chat_service.get_summary(
            chat_id=chat_id,
            user_id=user_id,
        )

        return self.context_builder.build(
            messages=messages,
            system_prompt=self.system_prompt,
            summary=summary,
        )

    async def _update_summary_if_needed(
        self,
        *,
        chat_id: UUID,
        user_id: UUID,
        context: ContextBuildResult,
    ) -> ContextBuildResult:
        if not context.should_summarize:
            return context

        if not context.omitted_messages:
            return context

        existing_summary = await self.chat_service.get_summary(
            chat_id=chat_id,
            user_id=user_id,
        )

        new_summary = await self.summary_service.summarize(
            messages=context.omitted_messages,
            existing_summary=existing_summary,
        )

        if new_summary and new_summary != existing_summary:
            await self.chat_service.update_summary(
                chat_id=chat_id,
                user_id=user_id,
                summary=new_summary,
            )
        else:
            new_summary = existing_summary

        # Rebuild context using the latest summary.
        messages = await self.message_service.get_llm_messages(
            chat_id=chat_id,
            user_id=user_id,
        )

        return self.context_builder.build(
            messages=messages,
            system_prompt=self.system_prompt,
            summary=new_summary,
        )

    async def _execute_tool_call(
        self,
        tool_call: ToolCall,
    ) -> str:
        tool = self.tool_registry.get(tool_call.tool_name)

        if tool is None:
            logger.error("Tool not found", extra={"tool_name": tool_call.tool_name})
            raise ToolNotFoundError()

        try:
            result = await tool.execute(tool_call.arguments)
        except Exception as ex:
            logger.exception(
                "Tool execution failed", extra={"tool_name": tool_call.tool_name}
            )
            raise ToolExecutionError() from ex

        return result.content

    async def _generate_with_retry(self, request: LLMRequest) -> LLMResponse:
        for attempt in range(self.MAX_PROVIDER_RETRIES + 1):
            try:
                return await self.provider.generate(request=request)
            except LLMProviderTransientError:
                logger.warning(
                    "Transient LLM provider error",
                    extra={
                        "attempt": attempt + 1,
                        "max_attempts": self.MAX_PROVIDER_RETRIES + 1,
                    },
                )

                if attempt >= self.MAX_PROVIDER_RETRIES:
                    raise

                await asyncio.sleep(2**attempt)
            except LLMProviderError:
                logger.exception("LLM provider error")
                raise

        raise LLMProviderError(message="LLM provider retry loop ended unexpectedly.")

    async def _generate_with_tools(
        self,
        messages: list[LLMMessage],
    ) -> LLMResponse:
        conversation = list(messages)
        tools = self.tool_registry.definitions()

        for _ in range(self.MAX_TOOL_ITERATIONS):
            response = await self._generate_with_retry(
                LLMRequest(messages=conversation, tools=tools)
            )

            if not response.tool_calls:
                return response

            # Preserve the model's tool-call decision
            # inside the in-memory conversation.
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
        self,
        chat_id: UUID,
        user_id: UUID,
        content: str,
    ) -> MessageRead:
        context = await self._prepare_conversation(
            chat_id=chat_id,
            user_id=user_id,
            content=content,
        )

        context = await self._update_summary_if_needed(
            chat_id=chat_id,
            user_id=user_id,
            context=context,
        )
        try:
            response = await self._generate_with_tools(
                messages=context.messages,
            )
        except Exception:
            logger.exception(
                "Conversation generation failed",
                extra={"chat_id": str(chat_id), "user_id": str(user_id)},
            )
            raise

        if not response.content:
            raise LLMProviderError()

        return await self.message_service.create_assistant_message(
            chat_id=chat_id,
            user_id=user_id,
            content=response.content,
        )

    def _sse_error(self, code: str, message: str) -> str:
        payload = json.dumps({"error": {"code": code, "message": message}})

        return f"event: error\ndata: {payload}\n\n"

    async def _stream_with_retry(self, request: LLMRequest) -> AsyncIterator[str]:
        for attempt in range(self.MAX_PROVIDER_RETRIES + 1):
            started = False

            try:
                async for token in self.provider.generate_stream(request):
                    started = True
                    yield token

                return

            except LLMProviderTransientError:
                if started or attempt >= self.MAX_PROVIDER_RETRIES:
                    raise

                logger.warning(
                    "Transient streaming provider error", extra={"attempt": attempt + 1}
                )

                await asyncio.sleep(2**attempt)

    async def stream_message(
        self,
        chat_id: UUID,
        user_id: UUID,
        content: str,
    ) -> AsyncIterator[str]:
        context = await self._prepare_conversation(
            chat_id=chat_id,
            user_id=user_id,
            content=content,
        )

        context = await self._update_summary_if_needed(
            chat_id=chat_id,
            user_id=user_id,
            context=context,
        )

        buffer: list[str] = []

        try:
            async for token in self._stream_with_retry(
                LLMRequest(
                    messages=context.messages,
                    tools=self.tool_registry.definitions(),
                )
            ):
                buffer.append(token)

                yield f"data: {token}\n\n"

        except asyncio.CancelledError:
            logger.info(
                "AI stream cancelled by client",
                extra={"chat_id": str(chat_id), "user_id": str(user_id)},
            )
            raise
        except LLMProviderTransientError as ex:
            logger.exception(
                "AI streaming failed",
                extra={"chat_id": str(chat_id), "user_id": str(user_id)},
            )
            yield self._sse_error(code=ex.code, message=ex.message)
            return

        except LLMProviderError as ex:
            yield self._sse_error(code=ex.code, message=ex.message)
            return

        except Exception:
            logger.exception(
                "Unexpected streaming error",
                extra={"chat_id": str(chat_id), "user_id": str(user_id)},
            )

            yield self._sse_error(
                code="AI_STREAM_ERROR",
                message="The AI response stream was interrupted.",
            )
            return

        if not buffer:
            yield self._sse_error(
                code="AI_EMPTY_RESPONSE",
                message="The AI provider returned an empty response.",
            )
            return

        final_content = "".join(buffer)

        if not final_content:
            logger.error(
                "AI stream completed without content",
                extra={"chat_id": str(chat_id), "user_id": str(user_id)},
            )

            yield self._sse_error(
                code="AI_EMPTY_RESPONSE",
                message="The AI provider returned an empty response.",
            )
            return

        await self.message_service.create_assistant_message(
            chat_id=chat_id,
            user_id=user_id,
            content=final_content,
        )
