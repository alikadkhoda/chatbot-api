from app.exceptions.base import AppException


class LLMProviderError(AppException):
    status_code = 503
    code = "LLM_PROVIDER_ERROR"
    message = "Failed to generate a response from the LLM provider."


class LLMProviderTransientError(LLMProviderError):
    code = "LLM_PROVIDER_TRANSIENT_ERROR"
    message = "The AI privider is temporarily unavailable."


class LLMProviderTimeoutError(LLMProviderTransientError):
    code = "LLM_PROVIDER_TIMEOUT"
    message = "The AI provider request timed out"


class LLMProviderRateLimitError(LLMProviderTransientError):
    code = "LLM_PROVIDER_RATE_LIMIT"
    message = "The AI provider rate limit was exceeded."
