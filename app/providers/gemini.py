from google import genai

from app.exceptions.provider import LLMProviderError
from app.providers.llm import LLMProvider
from app.providers.prompt_builder import build_prompt
from app.schemas.llm import LLMRequest, LLMResponse


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, default_model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._default_model = default_model

    async def generate(self, request: LLMRequest) -> LLMResponse:
        prompt = build_prompt(request.messages)
        try:
            response = await self._client.aio.models.generate_content(
                model=request.model or self._default_model, contents=prompt
            )
        except Exception as ex:
            raise LLMProviderError() from ex

        if response.text is None:
            raise LLMProviderError()

        return LLMResponse(content=response.text)
