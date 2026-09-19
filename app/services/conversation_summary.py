import logging
from uuid import UUID

from app.core.config import settings
from app.exceptions.rate_limit import (
    RateLimitExceededError,
    TokenLimitExceededError,
    UserQuotaExceededError,
)
from app.infrastructure.rate_limit.result import UsageReservation
from app.providers.llm import LLMProvider
from app.schemas.llm import (
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
)
from app.services.conversation_context import estimate_message_tokens, estimate_tokens
from app.services.rate_limit import RateLimitService

logger = logging.getLogger(__name__)


SUMMARY_SYSTEM_PROMPT = """You summarize conversation history for another AI assistant.

Preserve:
- important facts
- user preferences
- decisions
- unresolved questions
- relevant context

Do not invent facts.
Do not include tool-call syntax.
Keep the summary concise and useful.

Return only the summary text.
"""


class ConversationSummaryService:
    def __init__(
        self, provider: LLMProvider, rate_limit_service: RateLimitService
    ) -> None:
        self.provider = provider
        self.rate_limit_service = rate_limit_service

    def _format_message(self, message: LLMMessage) -> str:
        if message.role is LLMMessageRole.TOOL:
            return f"tool ({message.tool_name}): {message.content}"

        if message.role is LLMMessageRole.ASSISTANT and message.tool_calls:
            calls = ", ".join(call.tool_name for call in message.tool_calls)

            return f"assistant used tools: {calls}\n{message.content}"

        return f"{message.role.value}: {message.content}"

    async def summarize(
        self,
        *,
        user_id: UUID,
        messages: list[LLMMessage],
        existing_summary: str | None = None,
    ) -> str | None:
        # Nothing new to summarize.
        if not messages:
            return existing_summary

        prompt_parts: list[str] = []

        if existing_summary:
            prompt_parts.append(f"Existing summary:\n{existing_summary}")

        history = "\n\n".join(self._format_message(message) for message in messages)

        prompt_parts.append(f"New history to incorporate:\n{history}")

        request = LLMRequest(
            messages=[
                LLMMessage(
                    role=LLMMessageRole.SYSTEM,
                    content=SUMMARY_SYSTEM_PROMPT,
                ),
                LLMMessage(
                    role=LLMMessageRole.USER,
                    content="\n\n".join(prompt_parts),
                ),
            ]
        )

        try:
            input_tokens = sum(
                estimate_message_tokens(message) for message in request.messages
            )
            reservation: UsageReservation = (
                await self.rate_limit_service.check_cost_token_limit(
                    user_id=user_id,
                    input_tokens=input_tokens,
                    max_output_tokens=settings.ai.max_output_tokens,
                )
            )
            try:
                response = await self.provider.generate(request=request)
            except Exception:
                await self.rate_limit_service.release_usage(
                    user_id=user_id, reservation=reservation
                )
                raise

        except (
            RateLimitExceededError,
            TokenLimitExceededError,
            UserQuotaExceededError,
        ):
            raise

        except Exception:
            logger.exception(
                "Conversation summarization failed", extra={"user_id": str(user_id)}
            )
            return existing_summary

        if not response.content:
            logger.warning(
                "Conversation summarization returned no content",
                extra={"user_id": str(user_id)},
            )
            return existing_summary

        if response.usage is not None:
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
        else:
            input_tokens = input_tokens
            output_tokens = estimate_tokens(response.content)

        await self.rate_limit_service.record_provider_usage(
            user_id=user_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reservation=reservation,
        )

        return response.content.strip() or existing_summary
