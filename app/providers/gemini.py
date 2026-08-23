import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from google import genai
from google.genai import types

from app.exceptions.provider import LLMProviderError, LLMProviderTimeoutError
from app.providers.llm import LLMProvider
from app.providers.prompt_builder import build_prompt
from app.schemas.llm import (
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    LLMUsage,
)
from app.schemas.tool import ToolCall, ToolDefinition


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, default_model: str, timeout: float) -> None:
        self._client = genai.Client(api_key=api_key)
        self._default_model = default_model
        self._timeout = timeout

    async def generate(self, request: LLMRequest) -> LLMResponse:
        contents, system_instruction = self._contents(request.messages)
        config = self._config(request.tools, system_instruction)
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=request.model or self._default_model,
                    contents=contents,
                    config=config,
                ),
                timeout=self._timeout,
            )

            usage = None

            if response.usage_metadata:
                usage = LLMUsage(
                    input_tokens=response.usage_metadata.prompt_token_count or 0,
                    output_tokens=response.usage_metadata.candidates_token_count or 0,
                )

        except asyncio.TimeoutError as ex:
            raise LLMProviderTimeoutError() from ex

        except Exception as ex:
            raise LLMProviderError() from ex

        tool_calls = [
            ToolCall(
                id=function_call.id,
                tool_name=function_call.name,
                arguments=dict(function_call.args or {}),
            )
            for function_call in (response.function_calls or [])
            if function_call.name
        ]

        content = response.text or None

        if content is None and not tool_calls:
            raise LLMProviderError()

        return LLMResponse(content=response.text, tool_calls=tool_calls, usage=usage)

    async def generate_stream(
        self, request: LLMRequest
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        prompt = build_prompt(request.messages)

        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=request.model or self._default_model, contents=prompt
            )

            async for chunk in stream:
                if chunk.text:
                    yield chunk.text

        except Exception as ex:
            raise LLMProviderError() from ex

    def _contents(
        self, messages: list[LLMMessage]
    ) -> tuple[list[types.Content], list[str]]:
        contents: list[types.Content] = []
        system_instruction: list[str] = []

        for message in messages:
            if message.role is LLMMessageRole.SYSTEM:
                if message.content:
                    system_instruction.append(message.content)
                continue

            if message.role is LLMMessageRole.USER:
                contents.append(
                    types.Content(
                        role="user", parts=[types.Part.from_text(text=message.content)]
                    )
                )
                continue

            if message.role is LLMMessageRole.ASSISTANT:
                parts: list[types.Part] = []

                if message.content:
                    parts.append(types.Part.from_text(text=message.content))

                parts.extend(
                    types.Part.from_function_call(
                        name=tool_call.tool_name, args=tool_call.arguments
                    )
                    for tool_call in message.tool_calls
                )
                contents.append(types.Content(role="model", parts=parts))
                continue

            if message.role is LLMMessageRole.TOOL:
                if not message.tool_name:
                    raise LLMProviderError()
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=message.tool_name,
                                response={"result": message.content},
                            )
                        ],
                    )
                )

        return contents, system_instruction

    def _config(
        self, tools: list[ToolDefinition], system_instruction: list[str]
    ) -> types.GenerateContentConfig | None:
        if not tools and not system_instruction:
            return None

        kwargs: dict[str, Any] = {}

        if system_instruction:
            kwargs["system_instruction"] = system_instruction
        if tools:
            kwargs["tools"] = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=tool.name,
                            description=tool.description,
                            parameters_json_schema=tool.parameters,
                        )
                        for tool in tools
                    ]
                )
            ]
            kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
                disable=True
            )

        return types.GenerateContentConfig(**kwargs)
