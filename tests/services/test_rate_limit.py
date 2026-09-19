from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.exceptions.rate_limit import (
    RateLimitExceededError,
    TokenLimitExceededError,
    UserQuotaExceededError,
)
from app.infrastructure.rate_limit.result import (
    RequestRateLimitResult,
    UsageReservation,
    UsageReservationResult,
)
from app.infrastructure.rate_limit.store import RateLimitStore
from app.services.rate_limit import RateLimitService


@pytest.fixture
def store():
    return AsyncMock(spec=RateLimitStore)


@pytest.fixture
def service(store):
    return RateLimitService(
        store=store,
        max_requests_per_minute=5,
        max_requests_per_day=100,
        max_tokens_per_request=1000,
        max_tokens_per_day=5000,
        max_estimated_cost_per_day=10.0,
        input_cost_per_1k_tokens=1.0,
        output_cost_per_1k_tokens=2.0,
    )


def create_service(
    *,
    store: RateLimitStore,
    max_requests_per_minute: int = 20,
    max_requests_per_day: int = 200,
    max_tokens_per_request: int = 6000,
    max_tokens_per_day: int = 100_000,
    max_estimated_cost_per_day: float = 10.0,
    input_cost_per_1k_tokens: float = 0.01,
    output_cost_per_1k_tokens: float = 0.03,
) -> RateLimitService:
    return RateLimitService(
        store=store,
        max_requests_per_minute=max_requests_per_minute,
        max_requests_per_day=max_requests_per_day,
        max_tokens_per_request=max_tokens_per_request,
        max_tokens_per_day=max_tokens_per_day,
        max_estimated_cost_per_day=max_estimated_cost_per_day,
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
    )


@pytest.mark.asyncio
async def test_consume_request_allows_request(store):
    service = create_service(
        max_requests_per_minute=2, max_requests_per_day=100, store=store
    )
    user_id = uuid4()

    store.increment_request.return_value = RequestRateLimitResult(
        allowed=True, minute_current=1, daily_current=1
    )

    await service.consume_request(user_id)

    store.increment_request.assert_awaited_once_with(
        user_id=user_id, minute_limit=2, daily_limit=100
    )


@pytest.mark.asyncio
async def test_consume_request_rejects_minute_limit(store):
    service = create_service(
        max_requests_per_minute=2, max_requests_per_day=100, store=store
    )
    user_id = uuid4()

    store.increment_request.return_value = RequestRateLimitResult(
        allowed=False, minute_current=2, daily_current=2
    )

    with pytest.raises(RateLimitExceededError):
        await service.consume_request(user_id)

    store.increment_request.assert_awaited_once_with(
        user_id=user_id, minute_limit=2, daily_limit=100
    )


@pytest.mark.asyncio
async def test_consume_request_rejects_daily_request_quota(store):
    service = create_service(
        max_requests_per_minute=100, max_requests_per_day=2, store=store
    )
    user_id = uuid4()

    store.increment_request.return_value = RequestRateLimitResult(
        allowed=False, minute_current=2, daily_current=2
    )

    with pytest.raises(UserQuotaExceededError):
        await service.consume_request(user_id)

    store.increment_request.assert_awaited_once_with(
        user_id=user_id, minute_limit=100, daily_limit=2
    )


def test_estimate_cost(service):
    cost = service.estimate_cost(
        input_tokens=1000,
        output_tokens=500,
    )

    assert cost == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("input_tokens", "output_tokens"),
    [
        (-1, 0),
        (0, -1),
    ],
)
def test_estimate_cost_rejects_negative_tokens(
    service,
    input_tokens,
    output_tokens,
):
    with pytest.raises(ValueError):
        service.estimate_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


@pytest.mark.asyncio
async def test_check_cost_token_limit_returns_reservation(store):
    service = create_service(store=store)
    user_id = uuid4()

    store.reserve_usage.return_value = UsageReservationResult(
        allowed=True,
        token_current=800,
        cost_current=0.01,
    )

    reservation = await service.check_cost_token_limit(
        user_id=user_id,
        input_tokens=500,
        max_output_tokens=300,
    )

    assert reservation.tokens == 800
    assert reservation.cost == pytest.approx(
        service.estimate_cost(input_tokens=500, output_tokens=300)
    )

    call = store.reserve_usage.await_args

    assert call.kwargs["user_id"] == user_id
    assert call.kwargs["tokens"] == 800
    assert call.kwargs["cost"] == pytest.approx(
        service.estimate_cost(input_tokens=500, output_tokens=300)
    )

    assert call.kwargs["token_limit"] == 100_000
    assert call.kwargs["cost_limit"] == 10.0


@pytest.mark.asyncio
async def test_check_cost_token_limit_rejects_per_request_token_limit(store):
    service = create_service(
        store=store,
        max_tokens_per_request=1000,
    )

    with pytest.raises(TokenLimitExceededError):
        await service.check_cost_token_limit(
            user_id=uuid4(),
            input_tokens=800,
            max_output_tokens=300,
        )

    store.reserve_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_cost_token_limit_rejects_daily_token_quota(store):
    service = create_service(
        store=store,
        max_tokens_per_day=5000,
    )

    store.reserve_usage.return_value = UsageReservationResult(
        allowed=False,
        token_current=4800,
        cost_current=0.0,
    )

    with pytest.raises(TokenLimitExceededError):
        await service.check_cost_token_limit(
            user_id=uuid4(),
            input_tokens=400,
            max_output_tokens=200,
        )


@pytest.mark.asyncio
async def test_check_cost_token_limit_rejects_daily_cost_quota(store):
    service = create_service(
        store=store,
        max_estimated_cost_per_day=10.0,
    )

    store.reserve_usage.return_value = UsageReservationResult(
        allowed=False,
        token_current=1000,
        cost_current=9.0,
    )

    with pytest.raises(UserQuotaExceededError):
        await service.check_cost_token_limit(
            user_id=uuid4(),
            input_tokens=500,
            max_output_tokens=500,
        )


@pytest.mark.asyncio
async def test_record_provider_usage_settles_reservation(store):
    service = create_service(store=store)
    user_id = uuid4()

    reservation = UsageReservation(
        tokens=1000,
        cost=1.5,
    )

    await service.record_provider_usage(
        user_id=user_id,
        input_tokens=800,
        output_tokens=100,
        reservation=reservation,
    )

    store.settle_usage.assert_awaited_once_with(
        user_id=user_id,
        tokens=900,
        cost=pytest.approx(
            service.estimate_cost(
                input_tokens=800,
                output_tokens=100,
            )
        ),
        reserved_tokens=1000,
        reserved_cost=1.5,
    )


@pytest.mark.asyncio
async def test_release_usage_releases_reservation(store):
    service = create_service(store=store)
    user_id = uuid4()

    reservation = UsageReservation(
        tokens=1000,
        cost=1.5,
    )

    await service.release_usage(
        user_id=user_id,
        reservation=reservation,
    )

    store.release_usage.assert_awaited_once_with(
        user_id=user_id,
        reserved_tokens=1000,
        reserved_cost=1.5,
    )


@pytest.mark.asyncio
async def test_record_provider_usage_records_tokens_and_cost(
    service,
):
    user_id = uuid4()

    reservation = UsageReservation(
        tokens=2000,
        cost=1.5,
    )

    await service.record_provider_usage(
        user_id=user_id,
        input_tokens=1000,
        output_tokens=500,
        reservation=reservation,
    )

    expected_cost = service.estimate_cost(
        input_tokens=1000,
        output_tokens=500,
    )

    service.store.settle_usage.assert_awaited_once_with(
        user_id=user_id,
        tokens=1500,
        cost=expected_cost,
        reserved_tokens=2000,
        reserved_cost=1.5,
    )


@pytest.mark.asyncio
async def test_record_provider_usage_rejects_negative_input_tokens(
    service,
):
    reservation = UsageReservation(
        tokens=1000,
        cost=1.0,
    )

    with pytest.raises(ValueError):
        await service.record_provider_usage(
            user_id=uuid4(),
            input_tokens=-1,
            output_tokens=10,
            reservation=reservation,
        )

    service.store.settle_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_provider_usage_rejects_negative_output_tokens(
    service,
):
    reservation = UsageReservation(
        tokens=1000,
        cost=1.0,
    )

    with pytest.raises(ValueError):
        await service.record_provider_usage(
            user_id=uuid4(),
            input_tokens=10,
            output_tokens=-1,
            reservation=reservation,
        )

    service.store.settle_usage.assert_not_awaited()
