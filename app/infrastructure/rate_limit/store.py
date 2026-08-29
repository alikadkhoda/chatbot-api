from abc import ABC, abstractmethod
from uuid import UUID


class RateLimitStore(ABC):
    @abstractmethod
    async def get_request_count(self, user_id: UUID) -> int | None: ...

    @abstractmethod
    async def increment_request(self, user_id: UUID) -> int: ...

    @abstractmethod
    async def get_token_count(self, user_id: UUID) -> int | None: ...

    @abstractmethod
    async def increment_tokens(self, user_id: UUID, tokens: int) -> int: ...

    @abstractmethod
    async def get_cost(self, user_id: UUID) -> float | None: ...

    @abstractmethod
    async def increment_cost(self, user_id: UUID, cost: float) -> float: ...

    @abstractmethod
    async def delete_user(self, user_id: UUID) -> None: ...
