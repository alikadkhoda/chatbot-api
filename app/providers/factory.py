from app.core.config import AISetting
from app.providers.gemini import GeminiProvider
from app.providers.llm import LLMProvider
from app.providers.ollama import OllamaProvider
from app.schemas.llm_provider import AIProvider


class LLMProviderFactory:
    @staticmethod
    def create(settings: AISetting) -> LLMProvider:
        match settings.provider:
            case AIProvider.GEMINI:
                return GeminiProvider(
                    api_key=settings.gemini_api_key,
                    default_model=settings.default_model,
                )

            case AIProvider.OLLAMA:
                return OllamaProvider(
                    host=settings.ollama_host,
                    default_model=settings.default_model,
                    timeout=settings.request_timeout_seconds,
                )
