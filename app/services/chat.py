from uuid import UUID

from app.exceptions.chat import ChatNotFoundError
from app.models.chat import Chat
from app.repositories.chat import ChatRepository
from app.schemas.chat import ChatCreate, ChatRead, ChatUpdate


class ChatService:
    def __init__(self, repository: ChatRepository) -> None:
        self.repository = repository

    async def create_chat(self, data: ChatCreate, user_id: UUID) -> ChatRead:
        chat = Chat(user_id=user_id, title=data.title)

        chat = await self.repository.create(chat=chat)
        await self.repository.commit()
        await self.repository.refresh(chat)

        return ChatRead.model_validate(chat)

    async def get_chats(self, user_id: UUID) -> list[ChatRead]:
        chats = await self.repository.get_all_for_user(user_id)

        return [ChatRead.model_validate(chat) for chat in chats]

    async def get_chat(self, chat_id: UUID, user_id: UUID) -> ChatRead:
        chat = await self.repository.get_by_id_for_user(
            chat_id=chat_id, user_id=user_id
        )

        if chat is None:
            raise ChatNotFoundError()

        return ChatRead.model_validate(chat)

    async def chat_update(
        self, chat_id: UUID, data: ChatUpdate, user_id: UUID
    ) -> ChatRead:
        chat = await self.repository.get_by_id_for_user(
            chat_id=chat_id, user_id=user_id
        )

        if chat is None:
            raise ChatNotFoundError()

        if data.title is not None:
            chat.title = data.title

        await self.repository.commit()
        await self.repository.refresh(chat)

        return ChatRead.model_validate(chat)

    async def get_summary(self, chat_id: UUID, user_id: UUID) -> str | None:
        chat = await self.repository.get_by_id_for_user(
            chat_id=chat_id, user_id=user_id
        )

        if chat is None:
            raise ChatNotFoundError()
        return chat.summary

    async def update_summary(self, chat_id: UUID, user_id: UUID, summary: str) -> str:
        chat = await self.repository.get_by_id_for_user(
            chat_id=chat_id, user_id=user_id
        )

        if chat is None:
            raise ChatNotFoundError()

        chat.summary = summary

        await self.repository.commit()
        await self.repository.refresh(chat)

        return summary

    async def delete_chat(self, chat_id: UUID, user_id: UUID) -> None:
        chat = await self.repository.get_by_id_for_user(
            chat_id=chat_id, user_id=user_id
        )

        if chat is None:
            raise ChatNotFoundError()

        await self.repository.delete(chat)
        await self.repository.commit()
