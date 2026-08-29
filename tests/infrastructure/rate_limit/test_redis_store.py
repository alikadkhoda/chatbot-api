from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis

from app.core.config import settings
from app.infrastructure.rate_limit.redis_store import RedisRateLimitStore


@pytest_asyncio.fixture
async def redis() -> AsyncGenerator[Redis, None]:
    client = Redis.from_url(settings.redis_url, decode_responses=True)

    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def store(redis: Redis) -> RedisRateLimitStore:
    return RedisRateLimitStore(redis)


@pytest.mark.asyncio
async def test_request_count(store: RedisRateLimitStore) -> None:
    user_id = uuid4()

    try:
        assert await store.get_request_count(user_id) is None

        first_value = await store.increment_request(user_id)
        second_value = await store.increment_request(user_id)

        assert first_value == 1
        assert second_value == 2
        assert await store.get_request_count(user_id) == 2

    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_cost(store: RedisRateLimitStore) -> None:
    user_id = uuid4()

    try:
        assert await store.get_cost(user_id) is None

        first_value = await store.increment_cost(user_id, 0.10)
        second_value = await store.increment_cost(user_id, 0.25)

        assert first_value == pytest.approx(0.10)
        assert second_value == pytest.approx(0.35)
        assert await store.get_cost(user_id) == pytest.approx(0.35)
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_delete_user(store: RedisRateLimitStore) -> None:
    user_id = uuid4()

    await store.increment_request(user_id)
    await store.increment_tokens(user_id, 100)
    await store.increment_cost(user_id, 0.50)

    await store.delete_user(user_id)

    assert await store.get_request_count(user_id) is None
    assert await store.get_token_count(user_id) is None
    assert await store.get_cost(user_id) is None


@pytest.mark.asyncio
async def test_users_have_isolated_state(store: RedisRateLimitStore) -> None:
    user_a = uuid4()
    user_b = uuid4()

    try:
        await store.increment_request(user_a)
        await store.increment_request(user_a)

        await store.increment_request(user_b)

        assert await store.get_request_count(user_a) == 2
        assert await store.get_request_count(user_b) == 1
    finally:
        await store.delete_user(user_a)
        await store.delete_user(user_b)
