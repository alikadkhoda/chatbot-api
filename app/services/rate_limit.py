from uuid import UUID

from app.exceptions.rate_limit import (
    RateLimitExceededError,
    TokenLimitExceededError,
    UserQuotaExceededError,
)
from app.infrastructure.rate_limit.result import UsageReservation
from app.infrastructure.rate_limit.store import RateLimitStore


class RateLimitService:
    def __init__(
        self,
        store: RateLimitStore,
        max_requests_per_minute: int,
        max_requests_per_day: int,
        max_tokens_per_request: int,
        max_tokens_per_day: int,
        max_estimated_cost_per_day: float,
        input_cost_per_1k_tokens: float,
        output_cost_per_1k_tokens: float,
    ) -> None:
        self.store = store
        self.max_requests_per_minute = max_requests_per_minute
        self.max_requests_per_day = max_requests_per_day
        self.max_tokens_per_request = max_tokens_per_request
        self.max_tokens_per_day = max_tokens_per_day

        self.max_estimated_cost_per_day = max_estimated_cost_per_day
        self.input_cost_per_1k_tokens = input_cost_per_1k_tokens
        self.output_cost_per_1k_tokens = output_cost_per_1k_tokens

    # بررسی تعداد درخواست‌ها در دقیقه و روز
    async def consume_request(self, user_id: UUID) -> None:
        usage = await self.store.increment_request(
            user_id=user_id,
            minute_limit=self.max_requests_per_minute,
            daily_limit=self.max_requests_per_day,
        )

        if (
            usage.allowed is False
            and usage.minute_current == self.max_requests_per_minute
        ):
            raise RateLimitExceededError()

        if usage.allowed is False and usage.daily_current == self.max_requests_per_day:
            raise UserQuotaExceededError()

    # تخمین هزینه توکن‌ها در کل یک درخواست (توکن ورودی و خروجی)
    def estimate_cost(self, *, input_tokens: int, output_tokens: int) -> float:
        if input_tokens < 0:
            raise ValueError("input_tokens must be non-negative")

        if output_tokens < 0:
            raise ValueError("output_tokens must be non-negative")

        input_cost = (input_tokens / 1000) * self.input_cost_per_1k_tokens

        output_cost = (output_tokens / 1000) * self.output_cost_per_1k_tokens

        return input_cost + output_cost

    # بررسی تعداد توکن‌ها و هزینه مصرف شده کل توکن‌ها (ورودی و خروجی) در یک درخواست
    async def check_cost_token_limit(
        self, user_id: UUID, *, input_tokens: int, max_output_tokens: int
    ) -> UsageReservation:
        if input_tokens < 0:
            raise ValueError("input_tokens must be non-negative")

        if max_output_tokens < 0:
            raise ValueError("max_output_tokens must be non-negative")

        estimated_tokens = input_tokens + max_output_tokens

        if estimated_tokens > self.max_tokens_per_request:
            raise TokenLimitExceededError()

        estimated_cost = self.estimate_cost(
            input_tokens=input_tokens, output_tokens=max_output_tokens
        )

        result = await self.store.reserve_usage(
            user_id=user_id,
            tokens=estimated_tokens,
            cost=estimated_cost,
            token_limit=self.max_tokens_per_day,
            cost_limit=self.max_estimated_cost_per_day,
        )

        if not result.allowed:
            if result.token_current + estimated_tokens > self.max_tokens_per_day:
                raise TokenLimitExceededError()

            if (
                self.max_estimated_cost_per_day > 0
                and result.cost_current + estimated_cost
                > self.max_estimated_cost_per_day
            ):
                raise UserQuotaExceededError()

            raise UserQuotaExceededError()

        return UsageReservation(tokens=estimated_tokens, cost=estimated_cost)

    # ثبت مصرف توکن و هزینه آن با هم
    async def record_provider_usage(
        self,
        user_id: UUID,
        *,
        input_tokens: int,
        output_tokens: int,
        reservation: UsageReservation,
    ) -> None:
        if input_tokens < 0:
            raise ValueError("input_tokens must be non-negative")
        if output_tokens < 0:
            raise ValueError("output_tokens must be non-negative")

        actual_tokens = input_tokens + output_tokens
        actual_cost = self.estimate_cost(
            input_tokens=input_tokens, output_tokens=output_tokens
        )

        await self.store.settle_usage(
            user_id=user_id,
            tokens=actual_tokens,
            cost=actual_cost,
            reserved_tokens=reservation.tokens,
            reserved_cost=reservation.cost,
        )

    async def release_usage(self, user_id: UUID, reservation: UsageReservation) -> None:
        await self.store.release_usage(
            user_id=user_id,
            reserved_tokens=reservation.tokens,
            reserved_cost=reservation.cost,
        )
