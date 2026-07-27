from uuid import UUID

from sqlalchemy import select

from app.models.chat import Chat
from app.repositories.base import BaseRepository


class ChatRepository(BaseRepository):
    async def create(self, chat: Chat) -> Chat:
        self.session.add(chat)
        await self.session.flush()

        return chat

    async def get_by_id_for_user(self, chat_id: UUID, user_id: UUID) -> Chat | None:
        stmt = select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_all_for_user(self, user_id: UUID) -> list[Chat]:
        stmt = (
            select(Chat).where(Chat.user_id == user_id).order_by(Chat.created_at.desc())
        )

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def delete(self, chat: Chat) -> None:
        await self.session.delete(chat)
