from uuid import UUID

from sqlalchemy import select

from app.models.chat import Chat
from app.models.message import Message
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository):
    async def create(self, message: Message) -> Message:
        self.session.add(message)
        await self.session.flush()

        return message

    async def get_by_id_for_user(
        self, message_id: UUID, chat_id: UUID, user_id: UUID
    ) -> Message | None:
        stmt = (
            select(Message)
            .join(Chat, Chat.id == Message.chat_id)
            .where(
                Message.id == message_id,
                Message.chat_id == chat_id,
                Chat.user_id == user_id,
            )
        )
        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_all_for_chat(self, chat_id: UUID, user_id: UUID) -> list[Message]:
        stmt = (
            select(Message)
            .join(Chat, Chat.id == Message.chat_id)
            .where(Message.chat_id == chat_id, Chat.user_id == user_id)
            .order_by(Message.created_at.asc())
        )

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def delete(self, message: Message) -> None:
        await self.session.delete(message)
