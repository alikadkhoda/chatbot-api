from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.infrastructure.rate_limit.redis_store import RedisRateLimitStore
from app.infrastructure.rate_limit.store import RateLimitStoreUnavailableError


@pytest.fixture
def redis() -> AsyncMock:
    return AsyncMock(spec=Redis)


@pytest.fixture
def store(redis: AsyncMock) -> RedisRateLimitStore:
    return RedisRateLimitStore(redis)


@pytest.mark.asyncio
async def test_increment_request_maps_redis_failure(
    redis: AsyncMock, store: RedisRateLimitStore
):
    redis.eval.side_effect = RedisError("redis unavailable")

    with pytest.raises(RateLimitStoreUnavailableError):
        await store.increment_request(uuid4(), minute_limit=10, daily_limit=100)


@pytest.mark.asyncio
async def test_reserve_usage_maps_redis_failure(
    redis: AsyncMock, store: RedisRateLimitStore
):
    redis.eval.side_effect = RedisError("redis unavailable")

    with pytest.raises(RateLimitStoreUnavailableError):
        await store.reserve_usage(
            uuid4(),
            tokens=100,
            cost=0.1,
            token_limit=1000,
            cost_limit=10.0,
        )


@pytest.mark.asyncio
async def test_settle_usage_maps_redis_failure(
    redis: AsyncMock, store: RedisRateLimitStore
):
    redis.eval.side_effect = RedisError("redis unavailable")

    with pytest.raises(RateLimitStoreUnavailableError):
        await store.settle_usage(
            uuid4(),
            tokens=100,
            cost=0.1,
            reserved_tokens=120,
            reserved_cost=0.12,
        )


@pytest.mark.asyncio
async def test_release_usage_maps_redis_failure(
    redis: AsyncMock, store: RedisRateLimitStore
):
    redis.eval.side_effect = RedisError("redis unavailable")

    with pytest.raises(RateLimitStoreUnavailableError):
        await store.release_usage(uuid4(), reserved_tokens=120, reserved_cost=0.12)
