from uuid import UUID

from app.providers.llm import LLMProvider
from app.schemas.llm import LLMRequest
from app.schemas.message import MessageCreate, MessageRead
from app.services.chat import ChatService
from app.services.message import MessageService


class ConversationOrchestratorService:
    def __init__(
        self,
        chat_service: ChatService,
        message_service: MessageService,
        provider: LLMProvider,
    ) -> None:
        self.chat_service = chat_service
        self.message_service = message_service
        self.provider = provider

    async def send_message(
        self, chat_id: UUID, user_id: UUID, content: str
    ) -> MessageRead:
        await self.chat_service.get_chat(chat_id=chat_id, user_id=user_id)
        print(content)
        await self.message_service.create_user_message(
            chat_id=chat_id, user_id=user_id, data=MessageCreate(content=content)
        )

        messages = await self.message_service.get_llm_messages(
            chat_id=chat_id, user_id=user_id
        )

        response = await self.provider.generate(LLMRequest(messages=messages))

        assistant = await self.message_service.create_assistant_message(
            chat_id=chat_id, user_id=user_id, content=response.content
        )

        return assistant
