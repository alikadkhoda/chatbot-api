import pytest
from redis.asyncio import Redis

from app.database.redis import create_redis_client


@pytest.mark.asyncio
async def test_redis_connection() -> None:
    redis: Redis = create_redis_client()

    try:
        await redis.set("test:redis:connection", "ok")

        value = await redis.get("test:redis:connection")

        assert value == "ok"

    finally:
        await redis.delete("test:redis:connection")
        await redis.aclose()
