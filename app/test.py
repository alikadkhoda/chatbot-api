# from app.core.jwt import create_access_token, decode_token

# token = create_access_token(
#     subject="123e4567-e89b-12d3-a456-426614174000",
# )

# print(token)

# payload = decode_token("abc")

# print(payload)

# from datetime import datetime, timedelta, timezone

# from app.core.config import settings
# from app.core.jwt import decode_token

# import jwt


# expired_token = jwt.encode(
#     {
#         "sub": "123e4567-e89b-12d3-a456-426614174000",
#         "iat": datetime.now(timezone.utc) - timedelta(hours=2),
#         "exp": datetime.now(timezone.utc) - timedelta(hours=1),
#     },
#     settings.secret_key,
#     algorithm=settings.algorithm,
# )

# print(expired_token)

# try:
#     decode_token(expired_token)
# except Exception as exc:
#     print(type(exc).__name__)

# from datetime import datetime, timedelta, timezone

# import jwt

# from app.core.config import settings

# token = jwt.encode(
#     {
#         "iat": datetime.now(timezone.utc),
#         "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
#     },
#     settings.secret_key,
#     algorithm=settings.algorithm,
# )

# print(token)


# from app.schemas.llm import (
#     LLMMessage,
#     LLMMessageRole,
#     LLMRequest,
# )

# request = LLMRequest(
#     messages=[
#         LLMMessage(
#             role=LLMMessageRole.USER,
#             content="Hello",
#         )
#     ]
# )

# print(request)


# import asyncio

# from app.tools.bank_card_validator import BankCardValidatorTool
# from app.tools.registry import ToolRegistry


# async def main() -> None:
#     tool = BankCardValidatorTool()

#     result = await tool.execute(
#         {
#             "card_number": "6037991234567890",
#         }
#     )

#     assert result.content == "The bank card number is invalid."

#     registry = ToolRegistry([BankCardValidatorTool()])

#     tool = registry.get("validate_bank_card")
#     assert registry.get("validate_bank_card") is not None


# asyncio.run(main())

# import asyncio

# from app.providers.gemini import GeminiProvider
# from app.schemas.llm import LLMMessage, LLMMessageRole, LLMRequest


# async def main() -> None:
#     provider = GeminiProvider(api_key="...", default_model="gemini-2.5-flash")

#     response = await provider.generate(
#         LLMRequest(
#             messages=[
#                 LLMMessage(role=LLMMessageRole.USER,
#                            content="سلام. خودت را معرفی کن.")
#             ]
#         )
#     )

#     print(response.content)


# asyncio.run(main())
# import asyncio

# from app.providers.ollama import OllamaProvider
# from app.schemas.llm import LLMMessage, LLMMessageRole, LLMRequest


# async def main() -> None:
#     provider = OllamaProvider(
#         host="http://localhost:11434",
#         default_model="qwen3",
#     )

#     response = await provider.generate(
#         LLMRequest(
#             messages=[
#                 LLMMessage(
#                     role=LLMMessageRole.USER,
#                     content="سلام",
#                 )
#             ]
#         )
#     )

#     print(response.content)


# asyncio.run(main())


# from app.core.config import settings

# print(settings.ai.system_prompt)

import unittest

from app.schemas.llm import LLMMessage, LLMMessageRole
from app.schemas.tool import ToolCall
from app.services.conversation_context import ConversationContextBuilder


class ConversationContextBuilderTests(unittest.TestCase):
    def test_short_history_is_preserved_with_system_prompt(self) -> None:
        builder = ConversationContextBuilder(
            max_tokens=1000,
            reserve_tokens=100,
            summary_trigger_tokens=800,
        )
        messages = [
            LLMMessage(role=LLMMessageRole.USER, content="hello"),
            LLMMessage(role=LLMMessageRole.ASSISTANT, content="hi"),
        ]

        result = builder.build(messages, system_prompt="You are helpful.")

        self.assertEqual(result.omitted_messages, [])
        self.assertEqual(result.messages[0].role, LLMMessageRole.SYSTEM)
        self.assertEqual(len(result.messages), 3)

    def test_old_messages_are_trimmed(self) -> None:
        builder = ConversationContextBuilder(
            max_tokens=80,
            reserve_tokens=10,
            summary_trigger_tokens=50,
        )
        messages = [
            LLMMessage(role=LLMMessageRole.USER, content="old " * 20),
            LLMMessage(role=LLMMessageRole.ASSISTANT, content="old answer " * 20),
            LLMMessage(role=LLMMessageRole.USER, content="latest"),
        ]

        result = builder.build(messages, system_prompt="system")

        self.assertTrue(result.omitted_messages)
        self.assertEqual(result.messages[-1].content, "latest")

    def test_tool_call_and_results_are_kept_together(self) -> None:
        builder = ConversationContextBuilder(
            max_tokens=100,
            reserve_tokens=10,
            summary_trigger_tokens=60,
        )
        tool_assistant = LLMMessage(
            role=LLMMessageRole.ASSISTANT,
            content="",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    tool_name="validate_bank_card",
                    arguments={"card_number": "1234"},
                )
            ],
        )
        tool_result = LLMMessage(
            role=LLMMessageRole.TOOL,
            content="invalid",
            tool_name="validate_bank_card",
            tool_call_id="call-1",
        )
        messages = [
            LLMMessage(role=LLMMessageRole.USER, content="old " * 20),
            tool_assistant,
            tool_result,
            LLMMessage(role=LLMMessageRole.USER, content="latest"),
        ]

        result = builder.build(messages, system_prompt="system")
        selected = result.messages

        self.assertIn(tool_assistant, selected)
        self.assertIn(tool_result, selected)
        self.assertLess(selected.index(tool_assistant), selected.index(tool_result))


if __name__ == "__main__":
    unittest.main()
