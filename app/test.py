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
import asyncio

from app.providers.ollama import OllamaProvider
from app.schemas.llm import LLMMessage, LLMMessageRole, LLMRequest


async def main() -> None:
    provider = OllamaProvider(
        host="http://localhost:11434",
        default_model="qwen3",
    )

    response = await provider.generate(
        LLMRequest(
            messages=[
                LLMMessage(
                    role=LLMMessageRole.USER,
                    content="سلام",
                )
            ]
        )
    )

    print(response.content)


asyncio.run(main())
