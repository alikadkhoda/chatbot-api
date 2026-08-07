from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from app.schemas.llm import LLMRequest, LLMResponse


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    def generate_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]: ...
