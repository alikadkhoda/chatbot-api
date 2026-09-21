from app.exceptions.base import AppException


class RateLimitExceededError(AppException):
    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"
    message = "Rate limit exceeded. Please try again later."


class UserQuotaExceededError(AppException):
    status_code = 429
    code = "USER_QUOTA_EXCEEDED"
    message = "Your usage quota has been exceeded."


class TokenLimitExceededError(AppException):
    status_code = 429
    code = "TOKEN_LIMIT_EXCEEDED"
    message = "The token usage limit has been exceeded."


class RateLimitServiceUnavailableError(AppException):
    status_code = 503
    code = "RATE_LIMIT_SERVICE_UNAVAILABLE"
    message = "The rate limit service is temporarily unavailable."
