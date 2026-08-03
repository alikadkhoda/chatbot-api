from app.exceptions.base import AppException


class LLMProviderError(AppException):
    status_code = 503
    code = "LLM_PROVIDER_ERROR"
    message = "Failed to generate a response from the LLM provider."
