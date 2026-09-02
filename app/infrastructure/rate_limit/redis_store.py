import time
from decimal import Decimal
from uuid import UUID

from redis.asyncio import Redis

from app.infrastructure.rate_limit.result import RateLimitResult, RequestRateLimitResult
from app.infrastructure.rate_limit.store import RateLimitStore

REQUEST_WINDOW_SECONDS = 60
DAY_WINDOW_SECONDS = 24 * 60 * 60
COST_SCALE = 1_000_000

INCREMENT_REQUEST_SCRIPT = """
local minute_limit = tonumber(ARGV[1])
local daily_limit = tonumber(ARGV[2])

local minute_current = redis.call("GET", KEYS[1])
local daily_current = redis.call("GET", KEYS[2])

if not minute_current then
    minute_current = 0
else
    minute_current = tonumber(minute_current)
end

if not daily_current then
    daily_current = 0
else
    daily_current = tonumber(daily_current)
end

if minute_current >= minute_limit then
    return {0, minute_current, daily_current}
end

if daily_current >= daily_limit then
    return {0, minute_current, daily_current}
end

if minute_current == 0 then
    redis.call("SET", KEYS[1], 1, "EX", ARGV[3])
else
    redis.call("INCR", KEYS[1])
end

if daily_current == 0 then
    redis.call("SET", KEYS[2], 1, "EX", ARGV[4])
else
    redis.call("INCR", KEYS[2])
end

return {1, minute_current + 1, daily_current + 1}
"""

INCREMENT_AMOUNT_SCRIPT = """
local requested = tonumber(ARGV[2])
local limit = tonumber(ARGV[1])

if requested > limit then
    return {0, 0}
end

local current = redis.call("GET", KEYS[1])

if not current then
    redis.call("SET", KEYS[1], ARGV[2], "EX", ARGV[3])
    return {1, ARGV[2]}
end

current = tonumber(current)

if current + tonumber(ARGV[2]) > limit then
    return {0, current}
end

current = redis.call("INCRBY", KEYS[1], ARGV[2])

return {1, current}
"""


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

    # async def delete_user(self, user_id: UUID) -> None:
    #     now = int(time.time())
    #     minute_window = now // REQUEST_WINDOW_SECONDS
    #     daily_window = now // DAY_WINDOW_SECONDS

    #     await self._redis.delete(
    #     (
    #         f"rate_limit:user:{user_id}:"
    #         f"minute:request:{minute_window}"
    #     ),
    #     (
    #         f"rate_limit:user:{user_id}:"
    #         f"day:request:{daily_window}"
    #     ),
    #     (
    #         f"rate_limit:user:{user_id}:"
    #         f"day:token:{daily_window}"
    #     ),
    #     f"rate_limit:user:{user_id}:cost",
    # )

    async def delete_user(self, user_id: UUID) -> None:
        pattern = f"rate_limit:user:{user_id}:*"

        keys = [key async for key in self._redis.scan_iter(match=pattern)]

        if keys:
            await self._redis.delete(*keys)
