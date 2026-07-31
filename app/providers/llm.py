from typing import Protocol

from app.schemas.llm import LLMRequest, LLMResponse


class LLMProvider(Protocol):
    async def generate(self, request: LLMRequest) -> LLMResponse: ...
