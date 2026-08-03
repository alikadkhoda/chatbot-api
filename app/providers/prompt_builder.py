from app.schemas.llm import LLMMessage, LLMMessageRole


def build_prompt(messages: list[LLMMessage]) -> str:
    parts: list[str] = []

    for message in messages:
        match message.role:
            case LLMMessageRole.SYSTEM:
                role = "System"
            case LLMMessageRole.USER:
                role = "User"
            case LLMMessageRole.ASSISTANT:
                role = "Assistant"

        parts.append(f"{role}:\n{message.content}")

    return "\n\n".join(parts)
