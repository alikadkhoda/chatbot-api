from abc import ABC, abstractmethod

from app.schemas.llm import LLMRequest, LLMResponse


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse: ...
