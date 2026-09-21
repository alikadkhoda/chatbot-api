import time
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.infrastructure.rate_limit.result import (
    RateLimitResult,
    RequestRateLimitResult,
    UsageReservationResult,
)
from app.infrastructure.rate_limit.store import (
    RateLimitStore,
    RateLimitStoreUnavailableError,
)

SCRIPTS_DIR = Path(__file__).parent / "scripts"

REQUEST_WINDOW_SECONDS = 60
DAY_WINDOW_SECONDS = 24 * 60 * 60
COST_SCALE = 1_000_000

INCREMENT_REQUEST_SCRIPT = (SCRIPTS_DIR / "request.lua").read_text()

INCREMENT_AMOUNT_SCRIPT = (SCRIPTS_DIR / "amount.lua").read_text()

RESERVE_USAGE_SCRIPT = (SCRIPTS_DIR / "usage.lua").read_text()

SETTLE_USAGE_SCRIPT = (SCRIPTS_DIR / "settle.lua").read_text()

RELEASE_USAGE_SCRIPT = (SCRIPTS_DIR / "release.lua").read_text()


class RedisRateLimitStore(RateLimitStore):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get_request_minute_count(self, user_id: UUID) -> int | None:
        now = int(time.time())

        window = now // REQUEST_WINDOW_SECONDS

        key = f"rate_limit:user:{user_id}:minute:request:{window}"
        value = await self._redis.get(key)

        if value is None:
            return None

        return int(value)

    async def increment_request(
        self, user_id: UUID, minute_limit: int, daily_limit: int
    ) -> RequestRateLimitResult:
        now = int(time.time())
        minute_ttl = REQUEST_WINDOW_SECONDS - (now % REQUEST_WINDOW_SECONDS)
        daily_ttl = DAY_WINDOW_SECONDS - (now % DAY_WINDOW_SECONDS)

        minute_window = now // REQUEST_WINDOW_SECONDS
        daily_window = now // DAY_WINDOW_SECONDS

        minute_key = f"rate_limit:user:{user_id}:minute:request:{minute_window}"

        daily_key = f"rate_limit:user:{user_id}:day:request:{daily_window}"

        try:
            result = await self._redis.eval(
                INCREMENT_REQUEST_SCRIPT,
                2,
                minute_key,
                daily_key,
                minute_limit,
                daily_limit,
                minute_ttl,
                daily_ttl,
            )
        except RedisError as ex:
            raise RateLimitStoreUnavailableError() from ex

        return RequestRateLimitResult(
            allowed=bool(result[0]),
            minute_current=int(result[1]),
            daily_current=int(result[2]),
        )

    async def get_token_count(self, user_id: UUID) -> int | None:
        now = int(time.time())

        window = now // DAY_WINDOW_SECONDS

        key = f"rate_limit:user:{user_id}:day:token:{window}"
        value = await self._redis.get(key)

        if value is None:
            return None

        return int(value)

    async def increment_tokens(
        self, user_id: UUID, tokens: int, limit: int
    ) -> RateLimitResult:
        now = int(time.time())
        ttl = DAY_WINDOW_SECONDS - (now % DAY_WINDOW_SECONDS)

        window = now // DAY_WINDOW_SECONDS

        key = f"rate_limit:user:{user_id}:day:token:{window}"

        result = await self._redis.eval(
            INCREMENT_AMOUNT_SCRIPT, 1, key, limit, tokens, ttl
        )

        return RateLimitResult(
            allowed=bool(result[0]),
            current=int(result[1]),
        )

    async def get_cost(self, user_id: UUID) -> float | None:
        now = int(time.time())

        window = now // DAY_WINDOW_SECONDS

        key = f"rate_limit:user:{user_id}:day:cost:{window}"
        value = await self._redis.get(key)

        if value is None:
            return None

        return int(value) / COST_SCALE

    async def increment_cost(
        self, user_id: UUID, cost: float, limit: float
    ) -> RateLimitResult:
        scaled_cost = int(Decimal(str(cost)) * COST_SCALE)
        scaled_limit = int(Decimal(str(limit)) * COST_SCALE)

        now = int(time.time())
        ttl = DAY_WINDOW_SECONDS - (now % DAY_WINDOW_SECONDS)

        window = now // DAY_WINDOW_SECONDS

        key = f"rate_limit:user:{user_id}:day:cost:{window}"

        result = await self._redis.eval(
            INCREMENT_AMOUNT_SCRIPT, 1, key, scaled_limit, scaled_cost, ttl
        )

        return RateLimitResult(
            allowed=bool(result[0]),
            current=int(result[1]),
        )

    async def reserve_usage(
        self,
        user_id: UUID,
        tokens: int,
        cost: float,
        token_limit: int,
        cost_limit: float,
    ) -> UsageReservationResult:
        if tokens < 0:
            raise ValueError("tokens must be non-negative")

        if cost < 0:
            raise ValueError("cost must be non-negative")

        now = int(time.time())

        daily_ttl = DAY_WINDOW_SECONDS - (now % DAY_WINDOW_SECONDS)
        daily_window = now // DAY_WINDOW_SECONDS

        token_key = f"rate_limit:user:{user_id}:day:token:{daily_window}"
        reserved_token_key = (
            f"rate_limit:user:{user_id}:day:token_reserved:{daily_window}"
        )
        cost_key = f"rate_limit:user:{user_id}:day:cost:{daily_window}"
        reserved_cost_key = (
            f"rate_limit:user:{user_id}:day:cost_reserved:{daily_window}"
        )

        scaled_cost = int(Decimal(str(cost)) * COST_SCALE)
        scaled_limit = int(Decimal(str(cost_limit)) * COST_SCALE)

        try:
            result = await self._redis.eval(
                RESERVE_USAGE_SCRIPT,
                4,
                token_key,
                reserved_token_key,
                cost_key,
                reserved_cost_key,
                token_limit,
                tokens,
                scaled_limit,
                scaled_cost,
                daily_ttl,
            )
        except RedisError as ex:
            raise RateLimitStoreUnavailableError() from ex

        return UsageReservationResult(
            allowed=bool(result[0]),
            token_current=int(result[1]),
            cost_current=int(result[2]) / COST_SCALE,
        )

    async def settle_usage(
        self,
        user_id: UUID,
        tokens: int,
        cost: float,
        reserved_tokens: int,
        reserved_cost: float,
    ) -> None:
        if tokens < 0:
            raise ValueError("tokens must be non-negative")

        if cost < 0:
            raise ValueError("cost must be non-negative")

        if reserved_tokens < 0:
            raise ValueError("reserved_tokens must be non-negative")

        if reserved_cost < 0:
            raise ValueError("reserved_cost must be non-negative")

        now = int(time.time())

        daily_ttl = DAY_WINDOW_SECONDS - (now % DAY_WINDOW_SECONDS)
        daily_window = now // DAY_WINDOW_SECONDS

        token_key = f"rate_limit:user:{user_id}:day:token:{daily_window}"
        reserved_token_key = (
            f"rate_limit:user:{user_id}:day:token_reserved:{daily_window}"
        )
        cost_key = f"rate_limit:user:{user_id}:day:cost:{daily_window}"
        reserved_cost_key = (
            f"rate_limit:user:{user_id}:day:cost_reserved:{daily_window}"
        )

        scaled_cost = int(Decimal(str(cost)) * COST_SCALE)
        scaled_reserved_cost = int(Decimal(str(reserved_cost)) * COST_SCALE)

        try:
            await self._redis.eval(
                SETTLE_USAGE_SCRIPT,
                4,
                token_key,
                reserved_token_key,
                cost_key,
                reserved_cost_key,
                tokens,
                scaled_cost,
                reserved_tokens,
                scaled_reserved_cost,
                daily_ttl,
            )
        except RedisError as ex:
            raise RateLimitStoreUnavailableError() from ex

    async def release_usage(
        self, user_id: UUID, reserved_tokens: int, reserved_cost: float
    ) -> None:
        if reserved_tokens < 0:
            raise ValueError("tokens must be non-negative")

        if reserved_cost < 0:
            raise ValueError("cost must be non-negative")

        now = int(time.time())

        daily_ttl = DAY_WINDOW_SECONDS - (now % DAY_WINDOW_SECONDS)
        daily_window = now // DAY_WINDOW_SECONDS

        reserved_token_key = (
            f"rate_limit:user:{user_id}:day:token_reserved:{daily_window}"
        )
        reserved_cost_key = (
            f"rate_limit:user:{user_id}:day:cost_reserved:{daily_window}"
        )

        scaled_cost = int(Decimal(str(reserved_cost)) * COST_SCALE)

        try:
            await self._redis.eval(
                RELEASE_USAGE_SCRIPT,
                2,
                reserved_token_key,
                reserved_cost_key,
                reserved_tokens,
                scaled_cost,
                daily_ttl,
            )
        except RedisError as ex:
            raise RateLimitStoreUnavailableError() from ex

    async def delete_user(self, user_id: UUID) -> None:
        pattern = f"rate_limit:user:{user_id}:*"

        keys = [key async for key in self._redis.scan_iter(match=pattern)]

        if keys:
            await self._redis.delete(*keys)
