from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import decode_token
from app.database.session import get_session
from app.exceptions.auth import InactiveUserError, InvalidTokenError
from app.models.user import User
from app.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)
) -> User:
    payload = decode_token(token=token)

    subject = payload.get("sub")

    if subject is None:
        raise InvalidTokenError

    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise InvalidTokenError() from exc

    repository = UserRepository(session=session)
    user = await repository.get_by_id(user_id=user_id)

    if user is None:
        raise InvalidTokenError()

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise InactiveUserError()

    return current_user
