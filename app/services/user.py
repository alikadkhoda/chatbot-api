from app.core.security import hash_password
from app.exceptions.user import EmailAlreadyExistsError
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserRead


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def create_user(self, data: UserCreate) -> UserRead:
        existing_user = await self.repository.get_by_email(data.email)
        if existing_user is not None:
            raise EmailAlreadyExistsError()

        user = User(
            email=data.email,
            username=data.username,
            password_hash=hash_password(data.password.get_secret_value()),
        )

        user = await self.repository.create(user)
        await self.repository.commit()
        await self.repository.refresh(user)

        return UserRead.model_validate(user)
