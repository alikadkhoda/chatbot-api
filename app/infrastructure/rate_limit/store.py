from abc import ABC, abstractmethod
from uuid import UUID

from app.infrastructure.rate_limit.result import (
    RateLimitResult,
    RequestRateLimitResult,
    UsageReservationResult,
)


class RateLimitStore(ABC):
    @abstractmethod
    async def get_request_minute_count(self, user_id: UUID) -> int | None: ...

    @abstractmethod
    async def increment_request(
        self, user_id: UUID, minute_limit: int, daily_limit: int
    ) -> RequestRateLimitResult: ...

    @abstractmethod
    async def get_token_count(self, user_id: UUID) -> int | None: ...

    @abstractmethod
    async def increment_tokens(
        self, user_id: UUID, tokens: int, limit: int
    ) -> RateLimitResult: ...

    @abstractmethod
    async def get_cost(self, user_id: UUID) -> float | None: ...

    @abstractmethod
    async def increment_cost(
        self, user_id: UUID, cost: float, limit: float
    ) -> RateLimitResult: ...

    @abstractmethod
    async def reserve_usage(
        self,
        user_id: UUID,
        tokens: int,
        cost: float,
        token_limit: int,
        cost_limit: float,
    ) -> UsageReservationResult: ...

    @abstractmethod
    async def settle_usage(
        self,
        user_id: UUID,
        tokens: int,
        cost: float,
        reserved_tokens: int,
        reserved_cost: float,
    ) -> None: ...

    @abstractmethod
    async def release_usage(
        self, user_id: UUID, reserved_tokens: int, reserved_cost: float
    ) -> None: ...

    @abstractmethod
    async def delete_user(self, user_id: UUID) -> None: ...
