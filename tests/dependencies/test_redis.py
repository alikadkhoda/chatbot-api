from types import SimpleNamespace

from app.dependencies.redis import get_redis


def test_get_redis_return_app_redis() -> None:
    redis = object()

    app = SimpleNamespace(state=SimpleNamespace(redis=redis))

    request = SimpleNamespace(app=app)

    result = get_redis(request=request)

    assert result is redis
