from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, token: RefreshToken) -> RefreshToken:
        self.session.add(token)
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )

        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> None:
        token.revoked_at = datetime.now(timezone.utc)
