from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    current: int


@dataclass(frozen=True, slots=True)
class RequestRateLimitResult:
    allowed: bool
    minute_current: int
    daily_current: int
