import asyncio
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


########################START_OF_REQUEST_TESTS########################


@pytest.mark.asyncio
async def test_request_count(store: RedisRateLimitStore) -> None:
    user_id = uuid4()

    try:
        first = await store.increment_request(
            user_id,
            minute_limit=3,
            daily_limit=10,
        )
        second = await store.increment_request(
            user_id,
            minute_limit=3,
            daily_limit=10,
        )
        third = await store.increment_request(
            user_id,
            minute_limit=3,
            daily_limit=10,
        )
        fourth = await store.increment_request(
            user_id,
            minute_limit=3,
            daily_limit=10,
        )

        assert first.allowed is True
        assert first.minute_current == 1
        assert first.daily_current == 1

        assert second.allowed is True
        assert second.minute_current == 2
        assert second.daily_current == 2

        assert third.allowed is True
        assert third.minute_current == 3
        assert third.daily_current == 3

        assert fourth.allowed is False
        assert fourth.minute_current == 3
        assert fourth.daily_current == 3

    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_request_counter_has_ttl(
    redis: Redis, store: RedisRateLimitStore
) -> None:
    user_id = uuid4()

    try:
        result = await store.increment_request(user_id, minute_limit=3, daily_limit=10)

        assert result.allowed is True

        minute_keys = [
            key
            async for key in redis.scan_iter(
                match=f"rate_limit:user:{user_id}:minute:request:*"
            )
        ]
        daily_keys = [
            key
            async for key in redis.scan_iter(
                match=f"rate_limit:user:{user_id}:day:request:*"
            )
        ]
        assert len(minute_keys) == 1
        assert len(daily_keys) == 1

        minute_ttl = await redis.ttl(minute_keys[0])
        daily_ttl = await redis.ttl(daily_keys[0])

        assert 0 < minute_ttl <= 60
        assert 0 < daily_ttl <= 86400
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_rejected_request_does_not_reset_ttl(
    redis: Redis, store: RedisRateLimitStore
) -> None:
    user_id = uuid4()

    try:
        for _ in range(3):
            result = await store.increment_request(
                user_id, minute_limit=3, daily_limit=10
            )

            assert result.allowed is True

        minute_keys = [
            key
            async for key in redis.scan_iter(
                match=f"rate_limit:user:{user_id}:minute:request:*"
            )
        ]
        daily_keys = [
            key
            async for key in redis.scan_iter(
                match=f"rate_limit:user:{user_id}:day:request:*"
            )
        ]

        minute_ttl_before = await redis.ttl(minute_keys[0])
        daily_ttl_before = await redis.ttl(daily_keys[0])

        result = await store.increment_request(user_id, minute_limit=3, daily_limit=10)

        minute_ttl_after = await redis.ttl(minute_keys[0])
        daily_ttl_after = await redis.ttl(daily_keys[0])

        assert result.allowed is False
        assert result.minute_current == 3
        assert result.daily_current == 3
        assert minute_ttl_after <= minute_ttl_before
        assert daily_ttl_after <= daily_ttl_before
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_daily_rejection_does_not_increment_minute(
    store: RedisRateLimitStore,
) -> None:
    user_id = uuid4()

    try:
        for _ in range(3):
            result = await store.increment_request(
                user_id,
                minute_limit=100,
                daily_limit=3,
            )

            assert result.allowed is True

        result = await store.increment_request(
            user_id,
            minute_limit=100,
            daily_limit=3,
        )

        assert result.allowed is False
        assert result.minute_current == 3
        assert result.daily_current == 3

    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_concurrent_requests_respect_limit(store: RedisRateLimitStore) -> None:
    user_id = uuid4()
    minute_limit = 10
    daily_limit = 100

    try:
        results = await asyncio.gather(
            *(
                store.increment_request(
                    user_id, minute_limit=minute_limit, daily_limit=daily_limit
                )
                for _ in range(100)
            )
        )

        accepted = sum(result.allowed for result in results)
        rejected = sum(not result.allowed for result in results)

        assert accepted == 10
        assert rejected == 90

        final_result = await store.increment_request(
            user_id, minute_limit=minute_limit, daily_limit=daily_limit
        )

        assert final_result.allowed is False
        assert final_result.minute_current == 10
        assert final_result.daily_current == 10
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_daily_request_limit(
    store: RedisRateLimitStore,
) -> None:
    user_id = uuid4()

    try:
        results = await asyncio.gather(
            *(
                store.increment_request(
                    user_id,
                    minute_limit=100,
                    daily_limit=10,
                )
                for _ in range(20)
            )
        )

        accepted = sum(result.allowed for result in results)
        rejected = sum(not result.allowed for result in results)

        assert accepted == 10
        assert rejected == 10

        final_result = await store.increment_request(
            user_id,
            minute_limit=100,
            daily_limit=10,
        )

        assert final_result.allowed is False
        assert final_result.daily_current == 10

    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_get_request_minute_count(
    redis: Redis, store: RedisRateLimitStore
) -> None:
    user_id = uuid4()

    try:
        first = await store.increment_request(user_id, minute_limit=10, daily_limit=20)

        assert await store.get_request_minute_count(user_id) == 1
        assert first.allowed is True

    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_request_minute_resets_but_daily_continues(
    monkeypatch,
    store: RedisRateLimitStore,
) -> None:
    user_id = uuid4()

    try:
        current_time = 1_000_000

        monkeypatch.setattr(
            "app.infrastructure.rate_limit.redis_store.time.time",
            lambda: current_time,
        )

        first = await store.increment_request(
            user_id,
            minute_limit=2,
            daily_limit=5,
        )

        second = await store.increment_request(
            user_id,
            minute_limit=2,
            daily_limit=5,
        )

        assert first.allowed is True
        assert first.minute_current == 1
        assert first.daily_current == 1

        assert second.allowed is True
        assert second.minute_current == 2
        assert second.daily_current == 2

        # هنوز همان minute window هستیم
        third = await store.increment_request(
            user_id,
            minute_limit=2,
            daily_limit=5,
        )

        assert third.allowed is False
        assert third.minute_current == 2
        assert third.daily_current == 2

        # ورود به minute window بعدی
        current_time += 60

        fourth = await store.increment_request(
            user_id,
            minute_limit=2,
            daily_limit=5,
        )

        assert fourth.allowed is True
        assert fourth.minute_current == 1

        # minute reset شده، ولی daily ادامه پیدا کرده
        assert fourth.daily_current == 3

    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_daily_request_limit_is_enforced(
    store: RedisRateLimitStore,
) -> None:
    user_id = uuid4()

    try:
        first = await store.increment_request(
            user_id,
            minute_limit=20,
            daily_limit=3,
        )
        second = await store.increment_request(
            user_id,
            minute_limit=20,
            daily_limit=3,
        )
        third = await store.increment_request(
            user_id,
            minute_limit=20,
            daily_limit=3,
        )
        fourth = await store.increment_request(
            user_id,
            minute_limit=20,
            daily_limit=3,
        )

        assert first.allowed is True
        assert first.minute_current == 1
        assert first.daily_current == 1

        assert second.allowed is True
        assert second.minute_current == 2
        assert second.daily_current == 2

        assert third.allowed is True
        assert third.minute_current == 3
        assert third.daily_current == 3

        assert fourth.allowed is False
        assert fourth.minute_current == 3
        assert fourth.daily_current == 3

    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_daily_limit_rejection_does_not_increment_minute_counter(
    store: RedisRateLimitStore,
) -> None:
    user_id = uuid4()

    try:
        for _ in range(3):
            result = await store.increment_request(
                user_id,
                minute_limit=20,
                daily_limit=3,
            )
            assert result.allowed is True

        result = await store.increment_request(
            user_id,
            minute_limit=20,
            daily_limit=3,
        )

        assert result.allowed is False
        assert result.minute_current == 3
        assert result.daily_current == 3

    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_minute_limit_rejection_does_not_increment_daily_counter(
    store: RedisRateLimitStore,
) -> None:
    user_id = uuid4()

    try:
        for _ in range(3):
            result = await store.increment_request(
                user_id,
                minute_limit=3,
                daily_limit=20,
            )
            assert result.allowed is True

        result = await store.increment_request(
            user_id,
            minute_limit=3,
            daily_limit=20,
        )

        assert result.allowed is False
        assert result.minute_current == 3
        assert result.daily_current == 3

    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_request_counters_have_different_ttls(
    redis: Redis,
    store: RedisRateLimitStore,
) -> None:
    user_id = uuid4()

    try:
        result = await store.increment_request(
            user_id,
            minute_limit=20,
            daily_limit=100,
        )

        assert result.allowed is True

        minute_keys = [
            key
            async for key in redis.scan_iter(
                match=f"rate_limit:user:{user_id}:minute:request:*"
            )
        ]

        daily_keys = [
            key
            async for key in redis.scan_iter(
                match=f"rate_limit:user:{user_id}:day:request:*"
            )
        ]

        assert len(minute_keys) == 1
        assert len(daily_keys) == 1

        minute_ttl = await redis.ttl(minute_keys[0])
        daily_ttl = await redis.ttl(daily_keys[0])

        assert 0 < minute_ttl <= 60
        assert 0 < daily_ttl <= 86400
        assert daily_ttl > minute_ttl

    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_concurrent_requests_respect_minute_and_daily_limits(
    store: RedisRateLimitStore,
) -> None:
    user_id = uuid4()

    minute_limit = 100
    daily_limit = 10

    try:
        results = await asyncio.gather(
            *(
                store.increment_request(
                    user_id,
                    minute_limit=minute_limit,
                    daily_limit=daily_limit,
                )
                for _ in range(100)
            )
        )

        accepted = sum(result.allowed for result in results)
        rejected = sum(not result.allowed for result in results)

        assert accepted == 10
        assert rejected == 90

        final_result = await store.increment_request(
            user_id,
            minute_limit=minute_limit,
            daily_limit=daily_limit,
        )

        assert final_result.allowed is False
        assert final_result.minute_current == 10
        assert final_result.daily_current == 10

    finally:
        await store.delete_user(user_id)


########################END_OF_REQUEST_TESTS########################


########################START_OF_DAILY_TOKEN_TESTS########################


@pytest.mark.asyncio
async def test_token_count(store: RedisRateLimitStore) -> None:
    user_id = uuid4()

    try:
        first = await store.increment_tokens(user_id, tokens=20, limit=100)
        second = await store.increment_tokens(user_id, tokens=30, limit=100)
        third = await store.increment_tokens(user_id, tokens=40, limit=100)
        fourth = await store.increment_tokens(user_id, tokens=20, limit=100)
        assert first.allowed is True
        assert first.current == 20

        assert second.allowed is True
        assert second.current == 50

        assert third.allowed is True
        assert third.current == 90

        assert fourth.allowed is False
        assert fourth.current == 90
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_token_counter_has_ttl(redis: Redis, store: RedisRateLimitStore) -> None:
    user_id = uuid4()

    try:
        result = await store.increment_tokens(user_id, tokens=20, limit=100)

        assert result.allowed is True

        keys = [
            key
            async for key in redis.scan_iter(
                match=f"rate_limit:user:{user_id}:day:token:*"
            )
        ]

        assert len(keys) == 1

        ttl = await redis.ttl(keys[0])

        assert 0 < ttl <= 86400
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_rejected_request_for_token_day_does_not_reset_ttl(
    redis: Redis, store: RedisRateLimitStore
) -> None:
    user_id = uuid4()

    try:
        for _ in range(3):
            result = await store.increment_tokens(user_id, tokens=20, limit=100)

            assert result.allowed is True

        keys = [
            key
            async for key in redis.scan_iter(
                match=f"rate_limit:user:{user_id}:day:token:*"
            )
        ]

        ttl_before = await redis.ttl(keys[0])

        result = await store.increment_tokens(user_id, tokens=50, limit=100)

        ttl_after = await redis.ttl(keys[0])

        assert result.allowed is False
        assert result.current == 60
        assert ttl_after <= ttl_before
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_concurrent_requests_for_tokens_day_respect_limit(
    store: RedisRateLimitStore,
) -> None:
    user_id = uuid4()
    limit = 1000

    try:
        results = await asyncio.gather(
            *(
                store.increment_tokens(user_id, tokens=20, limit=limit)
                for _ in range(100)
            )
        )

        accepted = sum(result.allowed for result in results)
        rejected = sum(not result.allowed for result in results)

        assert accepted == 50
        assert rejected == 50

        final_result = await store.increment_tokens(user_id, tokens=20, limit=limit)

        assert final_result.allowed is False
        assert final_result.current == 1000
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_reject_tokens_exceeding_daily_limit(
    redis: Redis, store: RedisRateLimitStore
) -> None:
    user_id = uuid4()

    try:
        first = await store.increment_tokens(user_id, tokens=20, limit=10)

        keys = [
            key
            async for key in redis.scan_iter(
                match=f"rate_limit:user:{user_id}:day:token:*"
            )
        ]

        assert first.allowed is False
        assert first.current == 0
        assert len(keys) == 0
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_get_tokens_count(redis: Redis, store: RedisRateLimitStore) -> None:
    user_id = uuid4()

    try:
        first = await store.increment_tokens(user_id, tokens=20, limit=100)

        assert await store.get_token_count(user_id) == 20
        assert first.allowed is True

    finally:
        await store.delete_user(user_id)


########################END_OF_DAILY_TOKEN_TESTS########################


########################START_OF_DAILY_COST_TESTS########################
COST_SCALE = 1_000_000


@pytest.mark.asyncio
async def test_cost_count(store: RedisRateLimitStore) -> None:
    user_id = uuid4()

    try:
        first = await store.increment_cost(user_id, cost=0.20, limit=1)
        second = await store.increment_cost(user_id, cost=0.20, limit=1)
        third = await store.increment_cost(user_id, cost=0.20, limit=1)
        fourth = await store.increment_cost(user_id, cost=0.50, limit=1)
        assert first.allowed is True
        assert first.current == 200_000

        assert second.allowed is True
        assert second.current == 400_000

        assert third.allowed is True
        assert third.current == 600_000

        assert fourth.allowed is False
        assert fourth.current == 600_000
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_cost_counter_has_ttl(redis: Redis, store: RedisRateLimitStore) -> None:
    user_id = uuid4()

    try:
        result = await store.increment_cost(user_id, cost=0.20, limit=1)

        assert result.allowed is True

        keys = [
            key
            async for key in redis.scan_iter(
                match=f"rate_limit:user:{user_id}:day:cost:*"
            )
        ]

        assert len(keys) == 1

        ttl = await redis.ttl(keys[0])

        assert 0 < ttl <= 86400
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_rejected_cost_does_not_reset_ttl(
    redis: Redis, store: RedisRateLimitStore
) -> None:
    user_id = uuid4()

    try:
        for _ in range(3):
            result = await store.increment_cost(user_id, cost=0.20, limit=1)

            assert result.allowed is True

        keys = [
            key
            async for key in redis.scan_iter(
                match=f"rate_limit:user:{user_id}:day:cost:*"
            )
        ]

        ttl_before = await redis.ttl(keys[0])

        result = await store.increment_cost(user_id, cost=0.50, limit=1)

        ttl_after = await redis.ttl(keys[0])

        assert result.allowed is False
        assert result.current == 600_000
        assert ttl_after <= ttl_before
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_concurrent_cost_increments_respect_limit(
    store: RedisRateLimitStore,
) -> None:
    user_id = uuid4()
    limit = 10

    try:
        results = await asyncio.gather(
            *(store.increment_cost(user_id, cost=0.20, limit=limit) for _ in range(100))
        )

        accepted = sum(result.allowed for result in results)
        rejected = sum(not result.allowed for result in results)

        assert accepted == 50
        assert rejected == 50

        final_result = await store.increment_cost(user_id, cost=0.20, limit=limit)

        assert final_result.allowed is False
        assert final_result.current == 10000000
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_reject_cost_exceeding_daily_limit(
    redis: Redis, store: RedisRateLimitStore
) -> None:
    user_id = uuid4()

    try:
        first = await store.increment_cost(user_id, cost=2.0, limit=1.0)

        keys = [
            key
            async for key in redis.scan_iter(
                match=f"rate_limit:user:{user_id}:day:cost:*"
            )
        ]

        assert first.allowed is False
        assert first.current == 0
        assert len(keys) == 0
    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_get_cost_count(redis: Redis, store: RedisRateLimitStore) -> None:
    user_id = uuid4()

    try:
        first = await store.increment_cost(user_id, cost=0.20, limit=1)

        assert await store.get_cost(user_id) == 0.20
        assert first.allowed is True

    finally:
        await store.delete_user(user_id)


# @pytest.mark.asyncio
# async def test_cost(store: RedisRateLimitStore) -> None:
#     user_id = uuid4()

#     try:
#         assert await store.get_cost(user_id) is None

#         first_value = await store.increment_cost(user_id, 0.10)
#         second_value = await store.increment_cost(user_id, 0.25)

#         assert first_value == pytest.approx(0.10)
#         assert second_value == pytest.approx(0.35)
#         assert await store.get_cost(user_id) == pytest.approx(0.35)
#     finally:
#         await store.delete_user(user_id)

########################END_OF_DAILY_COST_TESTS########################


########################START_OF_DELETE_USER_TESTS########################

# @pytest.mark.asyncio
# async def test_delete_user(store: RedisRateLimitStore) -> None:
#     user_id = uuid4()

#     await store.increment_request(user_id, minute_limit=10, daily_limit=20)
#     await store.increment_tokens(user_id, tokens=100, limit=1000)
#     await store.increment_cost(user_id, 0.50)

#     await store.delete_user(user_id)

#     assert await store.get_request_minute_count(user_id) is None
#     assert await store.get_token_count(user_id) is None
#     assert await store.get_cost(user_id) is None


@pytest.mark.asyncio
async def test_delete_user_removes_all_rate_limit_keys(
    redis: Redis,
    store: RedisRateLimitStore,
) -> None:
    user_id = uuid4()

    prefix = f"rate_limit:user:{user_id}:"

    keys = [
        f"{prefix}minute:request:100",
        f"{prefix}minute:request:101",
        f"{prefix}day:request:50",
        f"{prefix}day:request:51",
        f"{prefix}day:token:50",
        f"{prefix}day:token:51",
        f"{prefix}day:cost:50",
    ]

    try:
        await redis.mset({key: "1" for key in keys})

        assert await redis.exists(*keys) == len(keys)

        await store.delete_user(user_id)

        assert await redis.exists(*keys) == 0

    finally:
        await store.delete_user(user_id)


@pytest.mark.asyncio
async def test_delete_user_does_not_remove_other_users_keys(
    redis: Redis,
    store: RedisRateLimitStore,
) -> None:
    user_a = uuid4()
    user_b = uuid4()

    key_a = f"rate_limit:user:{user_a}:minute:request:100"
    key_b = f"rate_limit:user:{user_b}:minute:request:100"

    try:
        await redis.set(key_a, 10)
        await redis.set(key_b, 20)

        await store.delete_user(user_a)

        assert await redis.exists(key_a) == 0
        assert await redis.exists(key_b) == 1
        assert await redis.get(key_b) == "20"

    finally:
        await store.delete_user(user_a)
        await store.delete_user(user_b)


########################END_OF_DELETE_USER_TESTS########################


@pytest.mark.asyncio
async def test_users_have_isolated_state(store: RedisRateLimitStore) -> None:
    user_a = uuid4()
    user_b = uuid4()

    try:
        await store.increment_request(user_a, minute_limit=10, daily_limit=20)
        await store.increment_request(user_a, minute_limit=10, daily_limit=20)

        await store.increment_request(user_b, minute_limit=10, daily_limit=20)

        assert await store.get_request_minute_count(user_a) == 2
        assert await store.get_request_minute_count(user_b) == 1
    finally:
        await store.delete_user(user_a)
        await store.delete_user(user_b)
