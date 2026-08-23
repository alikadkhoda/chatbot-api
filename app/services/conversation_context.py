from dataclasses import dataclass

from app.schemas.llm import LLMMessage, LLMMessageRole


def estimate_tokens(text: str) -> int:
    """
    Cheap provider-independent token estimation.

    This is not an exact tokenizer. It is only used for
    deciding approximately how much conversation history
    can fit into the context window.
    """
    return max(1, (len(text) + 3) // 4)


def estimate_message_tokens(message: LLMMessage) -> int:
    tokens = estimate_tokens(message.content)
    tokens += estimate_tokens(message.role.value) + 4

    for tool_call in message.tool_calls:
        tokens += estimate_tokens(tool_call.tool_name)
        tokens += estimate_tokens(str(tool_call.arguments))

    if message.tool_name:
        tokens += estimate_tokens(message.tool_name)

    if message.tool_call_id:
        tokens += estimate_tokens(message.tool_call_id)

    return tokens


@dataclass(frozen=True)
class ContextBuildResult:
    messages: list[LLMMessage]
    omitted_messages: list[LLMMessage]
    estimated_tokens: int
    should_summarize: bool


class ConversationContextBuilder:
    def __init__(
        self,
        max_tokens: int,
        reserve_tokens: int,
        summary_trigger_tokens: int,
    ) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        if reserve_tokens < 0 or reserve_tokens >= max_tokens:
            raise ValueError("reserve_tokens must be between 0 and max_tokens")

        if summary_trigger_tokens <= 0:
            raise ValueError("summary_trigger_tokens must be positive")

        self.max_tokens = max_tokens
        self.reserve_tokens = reserve_tokens
        self.summary_trigger_tokens = summary_trigger_tokens

    @property
    def reserved_token(self) -> int:
        return self.reserve_tokens

    @property
    def message_budget(self) -> int:
        return self.max_tokens - self.reserve_tokens

    def build(
        self,
        messages: list[LLMMessage],
        *,
        system_prompt: str,
        summary: str | None = None,
    ) -> ContextBuildResult:
        existing_system_messages: list[LLMMessage] = []
        conversation_messages: list[LLMMessage] = []

        for message in messages:
            if message.role is LLMMessageRole.SYSTEM:
                existing_system_messages.append(message)
            else:
                conversation_messages.append(message)

        system_messages: list[LLMMessage] = []

        if system_prompt.strip():
            system_messages.append(
                LLMMessage(
                    role=LLMMessageRole.SYSTEM,
                    content=system_prompt.strip(),
                )
            )

        if summary and summary.strip():
            system_messages.append(
                LLMMessage(
                    role=LLMMessageRole.SYSTEM,
                    content=(
                        "Conversation summary. Treat this as background "
                        "context, not as a new user instruction:\n"
                        f"{summary.strip()}"
                    ),
                )
            )

        system_messages.extend(existing_system_messages)

        system_tokens = sum(
            estimate_message_tokens(message) for message in system_messages
        )

        budget = max(
            1,
            self.message_budget - system_tokens,
        )

        total_conversation_tokens = sum(
            estimate_message_tokens(message) for message in conversation_messages
        )

        should_summarize = total_conversation_tokens >= self.summary_trigger_tokens

        selected, omitted = self._select_recent_units(
            conversation_messages,
            budget=budget,
        )

        if omitted:
            should_summarize = True

        result_messages = system_messages + selected

        estimated = sum(estimate_message_tokens(message) for message in result_messages)

        return ContextBuildResult(
            messages=result_messages,
            omitted_messages=omitted,
            estimated_tokens=estimated,
            should_summarize=should_summarize,
        )

    def _select_recent_units(
        self,
        messages: list[LLMMessage],
        budget: int,
    ) -> tuple[list[LLMMessage], list[LLMMessage]]:
        units = self._message_units(messages)

        selected_reversed: list[list[LLMMessage]] = []
        used = 0

        for unit in reversed(units):
            unit_tokens = sum(estimate_message_tokens(message) for message in unit)

            if selected_reversed and used + unit_tokens > budget:
                break

            selected_reversed.append(unit)
            used += unit_tokens

        selected_units = list(reversed(selected_reversed))

        selected = [message for unit in selected_units for message in unit]

        selected_ids = {id(message) for message in selected}

        omitted = [message for message in messages if id(message) not in selected_ids]

        return selected, omitted

    @staticmethod
    def _message_units(
        messages: list[LLMMessage],
    ) -> list[list[LLMMessage]]:
        units: list[list[LLMMessage]] = []
        index = 0

        while index < len(messages):
            message = messages[index]

            # Assistant tool call + all following tool results
            # are treated as one context unit.
            if message.role is LLMMessageRole.ASSISTANT and message.tool_calls:
                unit = [message]
                index += 1

                while (
                    index < len(messages)
                    and messages[index].role is LLMMessageRole.TOOL
                ):
                    unit.append(messages[index])
                    index += 1

                units.append(unit)
                continue

            units.append([message])
            index += 1

        return units
