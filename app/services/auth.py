from app.core.jwt import create_access_token
from app.core.security import verify_password
from app.exceptions.auth import InvalidCredentialsError
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse


class AuthService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def authenticate(self, data: LoginRequest) -> TokenResponse:
        user = await self.repository.get_by_email(data.email)

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

        return TokenResponse(access_token=access_token)
