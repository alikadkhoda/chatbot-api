from uuid import UUID

from app.exceptions.chat import ChatNotFoundError
from app.exceptions.message import MessageImmutableError, MessageNotFoundError
from app.models.message import Message, MessageRole
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.schemas.llm import LLMMessage, LLMMessageRole
from app.schemas.message import MessageCreate, MessageRead, MessageUpdate


class MessageService:
    def __init__(
        self, message_repository: MessageRepository, chat_repository: ChatRepository
    ) -> None:
        self.message_repository = message_repository
        self.chat_repository = chat_repository

    async def _create_message(
        self, *, chat_id: UUID, user_id: UUID, role: MessageRole, content: str
    ) -> Message:
        chat = await self.chat_repository.get_by_id_for_user(
            chat_id=chat_id, user_id=user_id
        )

        if chat is None:
            raise ChatNotFoundError()

        message = Message(chat_id=chat_id, role=role, content=content)

        message = await self.message_repository.create(message=message)

        await self.message_repository.commit()
        await self.message_repository.refresh(message)

        return message

    async def create_user_message(
        self, chat_id: UUID, user_id: UUID, data: MessageCreate
    ) -> MessageRead:
        message = await self._create_message(
            chat_id=chat_id,
            user_id=user_id,
            role=MessageRole.USER,
            content=data.content,
        )

        return MessageRead.model_validate(message)

    async def create_assistant_message(
        self, chat_id: UUID, user_id: UUID, content: str
    ) -> MessageRead:
        message = await self._create_message(
            chat_id=chat_id,
            user_id=user_id,
            role=MessageRole.ASSISTANT,
            content=content,
        )

        return MessageRead.model_validate(message)

    async def create_message(
        self, chat_id: UUID, user_id: UUID, data: MessageCreate
    ) -> MessageRead:
        return await self.create_user_message(
            chat_id=chat_id, user_id=user_id, data=data
        )

    async def get_messages(self, chat_id: UUID, user_id: UUID) -> list[MessageRead]:
        messages = await self.message_repository.get_all_for_chat(
            chat_id=chat_id, user_id=user_id
        )

        return [MessageRead.model_validate(message) for message in messages]

    async def get_message(
        self, chat_id: UUID, message_id: UUID, user_id: UUID
    ) -> MessageRead:
        message = await self.message_repository.get_by_id_for_user(
            chat_id=chat_id, message_id=message_id, user_id=user_id
        )

        if message is None:
            raise MessageNotFoundError()

        return MessageRead.model_validate(message)

    async def update_message(
        self, chat_id: UUID, message_id: UUID, user_id: UUID, data: MessageUpdate
    ) -> MessageRead:
        message = await self.message_repository.get_by_id_for_user(
            chat_id=chat_id, message_id=message_id, user_id=user_id
        )

        if message is None:
            raise MessageNotFoundError()

        if message.role is not MessageRole.USER:
            raise MessageImmutableError()

        if data.content is not None:
            message.content = data.content

        await self.message_repository.commit()
        await self.message_repository.refresh(message)

        return MessageRead.model_validate(message)

    async def delete_message(
        self, chat_id: UUID, message_id: UUID, user_id: UUID
    ) -> None:
        message = await self.message_repository.get_by_id_for_user(
            chat_id=chat_id, message_id=message_id, user_id=user_id
        )

        if message is None:
            raise MessageNotFoundError()

        if message.role is not MessageRole.USER:
            raise MessageImmutableError()

        await self.message_repository.delete(message=message)
        await self.message_repository.commit()

    async def get_llm_messages(self, chat_id: UUID, user_id: UUID) -> list[LLMMessage]:
        messages = await self.message_repository.get_all_for_chat(
            chat_id=chat_id, user_id=user_id
        )

        return [
            LLMMessage(role=LLMMessageRole(message.role.value), content=message.content)
            for message in messages
        ]
