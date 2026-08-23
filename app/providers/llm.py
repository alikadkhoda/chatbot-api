from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from app.schemas.llm import LLMRequest, LLMResponse, LLMStreamChunk


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    def generate_stream(
        self, request: LLMRequest
    ) -> AsyncGenerator[LLMStreamChunk, None]: ...
