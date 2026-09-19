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


@dataclass(frozen=True, slots=True)
class UsageReservationResult:
    allowed: bool
    token_current: int
    cost_current: float


@dataclass(frozen=True, slots=True)
class UsageReservation:
    tokens: int
    cost: float
