from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.exceptions.rate_limit import (
    RateLimitExceededError,
    TokenLimitExceededError,
    UserQuotaExceededError,
)


@dataclass
class UserUsage:
    minute_requests: int = 0
    daily_requests: int = 0
    daily_tokens: int = 0
    daily_estimated_cost: float = 0.0

    minute_started_at: datetime | None = None
    day_started_at: datetime | None = None


class RateLimitService:
    def __init__(
        self,
        max_requests_per_minute: int,
        max_requests_per_day: int,
        max_tokens_per_request: int,
        max_tokens_per_day: int,
        max_estimated_cost_per_day: float,
        input_cost_per_1k_tokens: float,
        output_cost_per_1k_tokens: float,
    ) -> None:
        self.max_requests_per_minute = max_requests_per_minute
        self.max_requests_per_day = max_requests_per_day
        self.max_tokens_per_request = max_tokens_per_request
        self.max_tokens_per_day = max_tokens_per_day

        self.max_estimated_cost_per_day = max_estimated_cost_per_day
        self.input_cost_per_1k_tokens = input_cost_per_1k_tokens
        self.output_cost_per_1k_tokens = output_cost_per_1k_tokens

        self._usage: dict[UUID, UserUsage] = {}

    # ریست پنجره‌های زمانی دقیقه و روز در صورت نیاز
    def _reset_windows_if_needed(self, usage: UserUsage, now: datetime) -> None:
        if (
            usage.minute_started_at is None
            or now - usage.minute_started_at >= timedelta(minutes=1)
        ):
            usage.minute_started_at = now
            usage.minute_requests = 0

        if usage.day_started_at is None or now - usage.day_started_at >= timedelta(
            days=1
        ):
            usage.day_started_at = now
            usage.daily_requests = 0
            usage.daily_tokens = 0
            usage.daily_estimated_cost = 0.0

    # بررسی تعداد درخواست‌ها در دقیقه و روز
    def consume_request(self, user_id: UUID) -> None:
        now = datetime.now(timezone.utc)

        usage = self._usage.setdefault(user_id, UserUsage())

        self._reset_windows_if_needed(usage=usage, now=now)

        if usage.minute_requests >= self.max_requests_per_minute:
            raise RateLimitExceededError()

        if usage.daily_requests >= self.max_requests_per_day:
            raise UserQuotaExceededError()

        usage.minute_requests += 1
        usage.daily_requests += 1

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
    def check_cost_token_limit(
        self, user_id: UUID, *, input_tokens: int, max_output_tokens: int
    ) -> None:
        total_tokens = input_tokens + max_output_tokens

        if total_tokens > self.max_tokens_per_request:
            raise TokenLimitExceededError()

        now = datetime.now(timezone.utc)

        usage = self._usage.setdefault(user_id, UserUsage())

        self._reset_windows_if_needed(usage=usage, now=now)

        estimated_cost = self.estimate_cost(
            input_tokens=input_tokens, output_tokens=max_output_tokens
        )

        if (
            usage.daily_estimated_cost + estimated_cost
            > self.max_estimated_cost_per_day
        ):
            raise UserQuotaExceededError()

        if usage.daily_tokens + total_tokens > self.max_tokens_per_day:
            raise UserQuotaExceededError()

    # # بررسی توکن‌های مصرف شده
    #     def check_token_limit(
    #             self, user_id: UUID, estimated_tokens: int
    #     ) -> None:
    #         if estimated_tokens <= 0:
    #             raise ValueError("estimated_tokens must be positive")

    #         if estimated_tokens > self.max_tokens_per_request:
    #             raise TokenLimitExceededError()

    #         now = datetime.now(timezone.utc)

    #         usage = self._usage.setdefault(
    #             user_id, UserUsage()
    #         )

    #         self._reset_windows_if_needed(
    #             usage=usage, now=now
    #         )

    #         if usage.daily_tokens + estimated_tokens > self.max_tokens_per_day:
    #             raise UserQuotaExceededError()

    # # ثبت توکن‌های مصرف شده
    # def record_token_usage(
    #         self,
    #         user_id: UUID,
    #         estimated_tokens: int
    # ) -> None:
    #     if estimated_tokens <= 0:
    #         raise ValueError("estimated_tokens must be positive")

    #     now = datetime.now(timezone.utc)

    #     usage = self._usage.setdefault(
    #         user_id,
    #         UserUsage()
    #     )

    #     self._reset_windows_if_needed(
    #         usage=usage,
    #         now=now
    #     )

    #     usage.daily_tokens += estimated_tokens
    # # ثبت هزینه توکن‌های مصرف شده در کل برای یک درخواست
    # def record_cost_usage(
    #         self, user_id: UUID, *, input_tokens: int, output_tokens: int
    # ) -> None:
    #     now = datetime.now(timezone.utc)

    #     usage = self._usage.setdefault(user_id, UserUsage())

    #     self._reset_windows_if_needed(
    #         usage=usage, now=now
    #     )

    #     cost = self.estimate_cost(
    #         input_tokens=input_tokens, output_tokens=output_tokens
    #     )

    #     usage.daily_estimated_cost += cost
    # ثبت مصرف توکن و هزینه آن با هم
    def record_provider_usage(
        self, user_id: UUID, *, input_tokens: int, output_tokens: int
    ) -> None:
        if input_tokens < 0:
            raise ValueError("input_tokens must be non-negative")
        if output_tokens < 0:
            raise ValueError("output_tokens must be non-negative")

        now = datetime.now(timezone.utc)

        usage = self._usage.setdefault(user_id, UserUsage())

        self._reset_windows_if_needed(usage=usage, now=now)

        usage.daily_tokens += input_tokens + output_tokens

        usage.daily_estimated_cost += self.estimate_cost(
            input_tokens=input_tokens, output_tokens=output_tokens
        )
