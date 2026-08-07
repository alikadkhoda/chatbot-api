from collections.abc import AsyncGenerator

from ollama import AsyncClient

from app.exceptions.provider import LLMProviderError
from app.providers.llm import LLMProvider
from app.schemas.llm import LLMRequest, LLMResponse


class OllamaProvider(LLMProvider):
    def __init__(self, host: str, default_model: str) -> None:
        self._client = AsyncClient(host=host)
        self._default_model = default_model

    async def generate(self, request: LLMRequest) -> LLMResponse:
        messages = self._messages(request=request)
        try:
            response = await self._client.chat(
                model=request.model or self._default_model, messages=messages
            )
        except Exception as ex:
            raise LLMProviderError() from ex

        content = response.message.content

        if not content:
            raise LLMProviderError()

        return LLMResponse(content=content)

    def _messages(self, request: LLMRequest):
        return [
            {"role": message.role.value, "content": message.content}
            for message in request.messages
        ]

    async def generate_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        messages = self._messages(request=request)

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
