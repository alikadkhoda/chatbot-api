from uuid import UUID

from sqlalchemy import select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        # stmt = select(User).where(User.id == user_id)

        # result = await self.session.execute(stmt)

        # return result.scalar_one_or_none()

        return await self.session.get(User, user_id)

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()

        return user

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
