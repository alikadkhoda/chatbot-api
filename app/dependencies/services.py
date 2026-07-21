from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.repositories.user import UserRepository
from app.services.auth import AuthService
from app.services.user import UserService


def get_user_service(
    session: AsyncSession = Depends(get_session),
) -> UserService:
    repository = UserRepository(session)

    return UserService(repository)


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    repository = UserRepository(session=session)

    return AuthService(repository=repository)
