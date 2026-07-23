import secrets
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.jwt import create_access_token
from app.core.security import hash_refresh_token, verify_password
from app.exceptions.auth import InvalidCredentialsError, InvalidTokenError
from app.models.refresh_token import RefreshToken
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        refresh_token_repository: RefreshTokenRepository,
    ) -> None:
        self.user_repository = user_repository
        self.refresh_token_repository = refresh_token_repository

    async def authenticate(self, data: LoginRequest) -> TokenResponse:
        user = await self.user_repository.get_by_email(data.email)

        if user is None:
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InvalidCredentialsError()

        is_password_valid = verify_password(
            data.password.get_secret_value(), user.password_hash
        )

        if not is_password_valid:
            raise InvalidCredentialsError()

        access_token = create_access_token(subject=str(user.id))

        refresh_token = secrets.token_urlsafe(64)

        refresh_token_model = RefreshToken(
            token_hash=hash_refresh_token(refresh_token),
            user_id=user.id,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(days=settings.refresh_token_expire_days)
            ),
        )

        await self.refresh_token_repository.create(refresh_token_model)

        await self.refresh_token_repository.commit()

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def refresh_access_token(self, raw_refresh_token: str) -> TokenResponse:
        token_hash = hash_refresh_token(raw_refresh_token)

        stored_token = await self.refresh_token_repository.get_by_hash(
            token_hash=token_hash
        )

        if stored_token is None:
            raise InvalidTokenError()

        now = datetime.now(timezone.utc)

        if stored_token.revoked_at is not None:
            raise InvalidTokenError()

        if stored_token.expires_at <= now:
            raise InvalidTokenError()

        user = await self.user_repository.get_by_id(stored_token.user_id)

        if user is None or not user.is_active:
            raise InvalidTokenError()

        await self.refresh_token_repository.revoke(stored_token)

        new_refresh_token = secrets.token_urlsafe(64)

        new_refresh_token_model = RefreshToken(
            token_hash=hash_refresh_token(new_refresh_token),
            user_id=user.id,
            expires_at=(now + timedelta(days=settings.refresh_token_expire_days)),
        )

        await self.refresh_token_repository.create(new_refresh_token_model)

        new_access_token = create_access_token(subject=str(user.id))

        await self.refresh_token_repository.commit()

        return TokenResponse(
            access_token=new_access_token, refresh_token=new_refresh_token
        )

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = hash_refresh_token(raw_refresh_token)

        stored_token = await self.refresh_token_repository.get_by_hash(token_hash)

        if stored_token is None:
            return

        if stored_token.revoked_at is not None:
            return

        await self.refresh_token_repository.revoke(stored_token)

        await self.refresh_token_repository.commit()
