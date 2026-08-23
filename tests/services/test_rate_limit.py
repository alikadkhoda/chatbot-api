from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.exceptions.rate_limit import (
    RateLimitExceededError,
    TokenLimitExceededError,
    UserQuotaExceededError,
)
from app.services.rate_limit import RateLimitService


@pytest.fixture
def service():
    return RateLimitService(
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
    max_requests_per_minute: int = 20,
    max_requests_per_day: int = 200,
    max_tokens_per_request: int = 6000,
    max_tokens_per_day: int = 100_000,
    max_estimated_cost_per_day: float = 10.0,
    input_cost_per_1k_tokens: float = 0.01,
    output_cost_per_1k_tokens: float = 0.03,
) -> RateLimitService:
    return RateLimitService(
        max_requests_per_minute=max_requests_per_minute,
        max_requests_per_day=max_requests_per_day,
        max_tokens_per_request=max_tokens_per_request,
        max_tokens_per_day=max_tokens_per_day,
        max_estimated_cost_per_day=max_estimated_cost_per_day,
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
    )


def test_consume_request_allows_requests_under_minute_limit():
    service = create_service(max_requests_per_minute=2)
    user_id = uuid4()

    service.consume_request(user_id)
    service.consume_request(user_id)

    usage = service._usage[user_id]

    assert usage.minute_requests == 2
    assert usage.daily_requests == 2


def test_consume_request_rejects_minute_limit():
    service = create_service(max_requests_per_minute=2)
    user_id = uuid4()

    service.consume_request(user_id)
    service.consume_request(user_id)

    with pytest.raises(RateLimitExceededError):
        service.consume_request(user_id)


def test_consume_request_rejects_daily_request_quota():
    service = create_service(max_requests_per_day=2)
    user_id = uuid4()

    service.consume_request(user_id)
    service.consume_request(user_id)

    with pytest.raises(UserQuotaExceededError):
        service.consume_request(user_id)


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


def test_check_cost_token_limit_allows_valid_request(service):
    user_id = uuid4()

    service.check_cost_token_limit(
        user_id=user_id,
        input_tokens=500,
        max_output_tokens=300,
    )


def test_check_cost_token_limit_rejects_per_request_token_limit(service):
    user_id = uuid4()

    with pytest.raises(TokenLimitExceededError):
        service.check_cost_token_limit(
            user_id=user_id,
            input_tokens=800,
            max_output_tokens=300,
        )


def test_check_cost_token_limit_rejects_daily_token_quota(service):
    user_id = uuid4()

    service.record_provider_usage(
        user_id=user_id,
        input_tokens=4000,
        output_tokens=500,
    )

    with pytest.raises(UserQuotaExceededError):
        service.check_cost_token_limit(
            user_id=user_id,
            input_tokens=400,
            max_output_tokens=200,
        )


def test_check_cost_token_limit_rejects_daily_cost_quota(service):
    user_id = uuid4()

    service.record_provider_usage(
        user_id=user_id,
        input_tokens=4000,
        output_tokens=1000,
    )

    with pytest.raises(UserQuotaExceededError):
        service.check_cost_token_limit(
            user_id=user_id,
            input_tokens=500,
            max_output_tokens=500,
        )


def test_record_provider_usage_records_tokens_and_cost(service):
    user_id = uuid4()

    service.record_provider_usage(
        user_id=user_id,
        input_tokens=1000,
        output_tokens=500,
    )

    usage = service._usage[user_id]

    assert usage.daily_tokens == 1500

    expected_cost = service.estimate_cost(
        input_tokens=1000,
        output_tokens=500,
    )

    assert usage.daily_estimated_cost == pytest.approx(expected_cost)


def test_record_provider_usage_rejects_negative_input_tokens(service):
    with pytest.raises(ValueError):
        service.record_provider_usage(
            user_id=uuid4(),
            input_tokens=-1,
            output_tokens=10,
        )


def test_record_provider_usage_rejects_negative_output_tokens(service):
    with pytest.raises(ValueError):
        service.record_provider_usage(
            user_id=uuid4(),
            input_tokens=10,
            output_tokens=-1,
        )


def test_consume_request_enforces_minute_limit_with_mocked_time(service):
    user_id = uuid4()
    fixed_time = datetime(2026, 1, 1, 12, 0, 0)

    with patch("app.services.rate_limit.datetime") as mock_datetime:
        # زمان را ثابت می‌کنیم
        mock_datetime.now.return_value = fixed_time

        # ۵ درخواست مجاز
        for _ in range(5):
            service.consume_request(user_id)

        # درخواست ششم باید خطا بدهد
        with pytest.raises(RateLimitExceededError):
            service.consume_request(user_id)

        # شبیه‌سازی گذشت ۱ دقیقه
        mock_datetime.now.return_value = fixed_time + timedelta(minutes=1)

        # حالا باید مجاز شود
        service.consume_request(user_id)  # خطا پرتاب نمی‌شود


def test_consume_request_enforces_daily_request_limit():
    service = RateLimitService(
        max_requests_per_minute=100,
        max_requests_per_day=2,
        max_tokens_per_request=1000,
        max_tokens_per_day=5000,
        max_estimated_cost_per_day=10.0,
        input_cost_per_1k_tokens=1.0,
        output_cost_per_1k_tokens=2.0,
    )

    user_id = uuid4()

    service.consume_request(user_id)
    service.consume_request(user_id)

    with pytest.raises(UserQuotaExceededError):
        service.consume_request(user_id)
