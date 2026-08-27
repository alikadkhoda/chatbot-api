from fastapi.testclient import TestClient

from app.main import app


def test_redis_lifecycle() -> None:
    with TestClient(app=app) as client:
        redis = client.app.state.redis

        assert redis is not None
        assert client.get("/").status_code == 200
