from uuid import UUID

from redis.asyncio import Redis

from app.infrastructure.rate_limit.store import RateLimitStore


class RedisRateLimitStore(RateLimitStore):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get_request_count(self, user_id: UUID) -> int | None:
        value = await self._redis.get(f"rate_limit:user:{user_id}:request")

        if value is None:
            return None

        return int(value)

    async def increment_request(self, user_id: UUID) -> int:
        return await self._redis.incr(f"rate_limit:user:{user_id}:request")

    async def get_token_count(self, user_id: UUID) -> int | None:
        value = await self._redis.get(f"rate_limit:user:{user_id}:token")

        if value is None:
            return None

        return int(value)

    async def increment_tokens(self, user_id: UUID, tokens: int) -> int:
        return await self._redis.incrby(f"rate_limit:user:{user_id}:token", tokens)

    async def get_cost(self, user_id: UUID) -> float | None:
        value = await self._redis.get(f"rate_limit:user:{user_id}:cost")

        if value is None:
            return None

        return float(value)

    async def increment_cost(self, user_id: UUID, cost: float) -> float:
        return await self._redis.incrbyfloat(f"rate_limit:user:{user_id}:cost", cost)

    async def delete_user(self, user_id: UUID) -> None:
        await self._redis.delete(
            f"rate_limit:user:{user_id}:request",
            f"rate_limit:user:{user_id}:token",
            f"rate_limit:user:{user_id}:cost",
        )
