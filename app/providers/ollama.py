import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from ollama import AsyncClient

from app.exceptions.provider import LLMProviderError, LLMProviderTimeoutError
from app.providers.llm import LLMProvider
from app.schemas.llm import LLMMessage, LLMMessageRole, LLMRequest, LLMResponse
from app.schemas.tool import ToolCall, ToolDefinition


class OllamaProvider(LLMProvider):
    def __init__(self, host: str, default_model: str, timeout: float) -> None:
        self._client = AsyncClient(host=host)
        self._default_model = default_model
        self._timeout = timeout

    async def generate(self, request: LLMRequest) -> LLMResponse:
        messages = self._messages(messages=request.messages)
        tools = self._tools(request.tools)

        print("MESSAGES:", messages)
        print("TOOLS:", tools)

        try:
            response = await asyncio.wait_for(
                self._client.chat(
                    model=request.model or self._default_model,
                    messages=messages,
                    tools=tools or None,
                    think=False,
                ),
                timeout=self._timeout,
            )

        except asyncio.TimeoutError as ex:
            raise LLMProviderTimeoutError() from ex

        except Exception as ex:
            raise LLMProviderError() from ex

        content = response.message.content or None

        tool_calls = [
            ToolCall(
                tool_name=tool_call.function.name,
                arguments=dict(tool_call.function.arguments),
            )
            for tool_call in (response.message.tool_calls or [])
        ]

        if content is None and not tool_calls:
            raise LLMProviderError()

        return LLMResponse(content=content, tool_calls=tool_calls)

    async def generate_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        messages = self._messages(messages=request.messages)

        try:
            stream = await self._client.chat(
                model=request.model or self._default_model,
                messages=messages,
                stream=True,
                think=False,
            )

            async for chunk in stream:
                content = chunk.message.content

                if content:
                    yield content

        except Exception as ex:
            raise LLMProviderError() from ex

    def _messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        for message in messages:
            if message.role is LLMMessageRole.ASSISTANT:
                item: dict[str, Any] = {"role": "assistant", "content": message.content}
                if message.tool_calls:
                    item["tool_calls"] = [
                        {
                            "function": {
                                "name": tool_call.tool_name,
                                "arguments": tool_call.arguments,
                            }
                        }
                        for tool_call in message.tool_calls
                    ]
                result.append(item)
                continue
            item: dict[str, Any] = {
                "role": message.role.value,
                "content": message.content,
            }
            if message.role is LLMMessageRole.TOOL and message.tool_name:
                item["tool_name"] = message.tool_name
            result.append(item)
        return result

    def _tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]
