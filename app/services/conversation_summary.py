import logging

from app.providers.llm import LLMProvider
from app.schemas.llm import (
    LLMMessage,
    LLMMessageRole,
    LLMRequest,
)

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
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def _format_message(self, message: LLMMessage) -> str:
        if message.role is LLMMessageRole.TOOL:
            return f"tool ({message.tool_name}): {message.content}"

        if message.role is LLMMessageRole.ASSISTANT and message.tool_calls:
            calls = ", ".join(call.tool_name for call in message.tool_calls)

            return f"assistant used tools: {calls}\n{message.content}"

        return f"{message.role.value}: {message.content}"

    async def summarize(
        self,
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
            response = await self.provider.generate(request=request)
        except Exception:
            logger.exception("Conversation summarization failed")
            return existing_summary

        if not response.content:
            logger.warning("Conversation summarization returned no content")
            return existing_summary

        return response.content.strip() or existing_summary
