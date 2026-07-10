from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Base class for all repositories."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
